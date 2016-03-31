#!/usr/bin/env python
#
# Copyright (c) 2014, Georgia Tech Research Corporation
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the Georgia Tech Research Corporation nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY GEORGIA TECH RESEARCH CORPORATION ''AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL GEORGIA TECH BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# system
import rospy
import random
import os, sys, threading

# util
import numpy as np
import hrl_lib.quaternion as qt
from hrl_anomaly_detection import util
from hrl_anomaly_detection import data_manager as dm
from sound_play.libsoundplay import SoundClient

# learning
from hrl_anomaly_detection.hmm import learning_hmm

# Classifier
from hrl_anomaly_detection.classifiers import classifier as cb
from sklearn import preprocessing
from joblib import Parallel, delayed

# msg
from hrl_srvs.srv import Bool_None, Bool_NoneResponse
from hrl_anomaly_detection.msg import MultiModality
from std_msgs.msg import String

class anomaly_detector:
    def __init__(self, subject_names, task_name, check_method, raw_data_path, save_data_path,\
                 param_dict):
        ## rospy.init_node(task_name)
        rospy.loginfo('Initializing anomaly detector')

        self.subject_names     = subject_names
        self.task_name         = task_name
        self.raw_data_path     = raw_data_path
        self.save_data_path    = save_data_path

        self.enable_detector = False
        self.soundHandle = SoundClient()
        self.dataList = []

        # Params
        self.param_dict = param_dict        
        self.classifier_method = check_method
        
        self.nEmissionDim = None
        self.ml = None
        self.classifier = None

        # Comms
        self.lock = threading.Lock()        

        self.initParams()
        self.initComms()
        self.initDetector()
        self.reset()

    '''
    Load feature list
    '''
    def initParams(self):

        if False:
            # data
            self.rf_radius = rospy.get_param('/hrl_manipulation_task/'+self.task_name+'/rf_radius')
            self.rf_center = rospy.get_param('/hrl_manipulation_task/'+self.task_name+'/rf_center')
            self.downSampleSize = rospy.get_param('/hrl_manipulation_task/'+self.task_name+'/downSampleSize')
            self.handFeatures = rospy.get_param('/hrl_manipulation_task/'+self.task_name+'/feature_list')
            self.data_ext = False
            self.nNormalFold   = 2
            self.nAbnormalFold = 2

            # Generative modeling
            self.nState = rospy.get_param('/hrl_anomaly_detection/'+self.task_name+'/states')
            self.cov    = rospy.get_param('/hrl_anomaly_detection/'+self.task_name+'/cov_mult')
            self.scale  = rospy.get_param('/hrl_anomaly_detection/'+self.task_name+'/scale')

            self.SVM_dict = None
        else:
            self.rf_radius = self.param_dict['data_param']['local_range']
            self.rf_center = self.param_dict['data_param']['rf_center']
            self.downSampleSize = self.param_dict['data_param']['downSampleSize']
            self.handFeatures = self.param_dict['data_param']['handFeatures']
            self.data_ext     = self.param_dict['data_param']['lowVarDataRemv']
            self.cut_data     = self.param_dict['data_param']['cut_data']
            self.nNormalFold   = self.param_dict['data_param']['nNormalFold']
            self.nAbnormalFold = self.param_dict['data_param']['nAbnormalFold']

            self.nState = self.param_dict['HMM']['nState']
            self.cov    = self.param_dict['HMM']['cov']
            self.scale  = self.param_dict['HMM']['scale']

            self.SVM_dict  = self.param_dict['SVM']


        # Discriminative classifier
        ## self.threshold = -200.0

    '''
    Subscribe raw data
    '''
    def initComms(self):
        # Publisher
        self.action_interruption_pub = rospy.Publisher('/hrl_manipulation_task/InterruptAction', String)
        self.task_interruption_pub   = rospy.Publisher("/manipulation_task/emergency", String)

        # Subscriber
        rospy.Subscriber('/hrl_manipulation_task/raw_data', MultiModality, self.rawDataCallback)
        # sensitiviy control topic

        # Service
        self.detection_service = rospy.Service('anomaly_detector_enable/' + self.task_name, Bool_None, self.enablerCallback)

    def initDetector(self):

        dd = dm.getDataSet(self.subject_names, self.task_name, self.raw_data_path, \
                           self.save_data_path, self.rf_center, \
                           self.rf_radius,\
                           downSampleSize=self.downSampleSize, \
                           scale=1.0,\
                           ae_data=False,\
                           data_ext=self.data_ext,\
                           handFeatures=self.handFeatures, \
                           cut_data=self.cut_data,\
                           data_renew=False)

        self.handFeatureParams = dd['param_dict']
                           
        # Task-oriented hand-crafted features        
        kFold_list = dm.kFold_data_index2(len(dd['successData'][0]), len(dd['failureData'][0]), \
                                              self.nNormalFold, self.nAbnormalFold )
        (normalTrainIdx, abnormalTrainIdx, normalTestIdx, abnormalTestIdx) = kFold_list[0]


        # dim x sample x length # TODO: what is the best selection?
        normalTrainData   = dd['successData'][:, normalTrainIdx, :] * self.scale
        abnormalTrainData = dd['failureData'][:, abnormalTrainIdx, :] * self.scale # will not be used...?
        normalTestData    = dd['successData'][:, normalTestIdx, :] * self.scale
        abnormalTestData  = dd['failureData'][:, abnormalTestIdx, :] * self.scale

        # training hmm
        self.nEmissionDim   = len(normalTrainData)
        detection_param_pkl = os.path.join(self.save_data_path, 'hmm_'+self.task_name+'_demo.pkl')
        self.ml = learning_hmm.learning_hmm(self.nState, self.nEmissionDim, verbose=False)
        ret = self.ml.fit(normalTrainData, cov_mult=[self.cov]*(self.nEmissionDim**2),
                          ml_pkl=detection_param_pkl, use_pkl=True)

        if ret == 'Failure':
            print "-------------------------"
            print "HMM returned failure!!   "
            print "-------------------------"
            sys.exit()

        #-----------------------------------------------------------------------------------------
        # Classifier test data
        #-----------------------------------------------------------------------------------------
        testDataX = []
        testDataY = []
        for i in xrange(self.nEmissionDim):
            temp = np.vstack([normalTestData[i], abnormalTestData[i]])
            testDataX.append( temp )

        testDataY = np.hstack([ -np.ones(len(normalTestData[0])), \
                                np.ones(len(abnormalTestData[0])) ])

        startIdx = 4
        r = Parallel(n_jobs=-1)(delayed(learning_hmm.computeLikelihoods)(i, self.ml.A, self.ml.B, \
                                                                         self.ml.pi, self.ml.F,
                                                                         [ testDataX[j][i] for j in xrange(self.nEmissionDim) ],
                                                                self.ml.nEmissionDim, self.ml.nState,
                                                                startIdx=startIdx, bPosterior=True)
                                                                for i in xrange(len(testDataX[0])))
        _, ll_classifier_test_idx, ll_logp, ll_post = zip(*r)

        # nSample x nLength
        ll_classifier_test_X = []
        ll_classifier_test_Y = []
        for i in xrange(len(ll_logp)):
            l_X = []
            l_Y = []
            for j in xrange(len(ll_logp[i])):        
                l_X.append( [ll_logp[i][j]] + ll_post[i][j].tolist() )

                if testDataY[i] > 0.0: l_Y.append(1)
                else: l_Y.append(-1)

            ll_classifier_test_X.append(l_X)
            ll_classifier_test_Y.append(l_Y)


        # flatten the data
        X_test_org = []
        Y_test_org = []
        idx_test_org = []
        for i in xrange(len(ll_classifier_test_X)):
            for j in xrange(len(ll_classifier_test_X[i])):
                X_test_org.append(ll_classifier_test_X[i][j])
                Y_test_org.append(ll_classifier_test_Y[i][j])
                idx_test_org.append(ll_classifier_test_idx[i][j])


        # data preparation
        self.scaler = preprocessing.StandardScaler()
        if 'svm' in self.classifier_method:
            X_scaled = self.scaler.fit_transform(X_test_org)
        else:
            X_scaled = X_test_org
        print self.classifier_method, " : Before classification : ", np.shape(X_scaled), np.shape(Y_test_org)

        # Fit Classifier
        self.classifier = cb.classifier(method=self.classifier_method, nPosteriors=self.nState, \
                                        nLength=len(normalTrainData[0][0]) - startIdx )
        self.classifier.set_params(**self.SVM_dict)
        self.classifier.fit(X_scaled, Y_test_org, idx_test_org)

        #TEMP
        self.tempdata = normalTrainData[:,0:1,:]
        return


        
    def enablerCallback(self, msg):

        if msg.data is True:
            self.enable_detector = True
        else:
            # Reset detector
            self.enable_detector = False
            self.reset()

        return Bool_NoneResponse()

    def rawDataCallback(self, msg):
        
        self.audio_feature     = msg.audio_feature
        self.audio_power       = msg.audio_power
        self.audio_azimuth     = msg.audio_azimuth
        self.audio_head_joints = msg.audio_head_joints
        self.audio_cmd         = msg.audio_cmd

        self.audio_wrist_rms   = msg.audio_wrist_rms
        self.audio_wrist_mfcc  = msg.audio_wrist_mfcc

        self.kinematics_ee_pos      = msg.kinematics_ee_pos
        self.kinematics_ee_quat     = msg.kinematics_ee_quat
        self.kinematics_jnt_pos     = msg.kinematics_jnt_pos
        self.kinematics_jnt_vel     = msg.kinematics_jnt_vel
        self.kinematics_jnt_eff     = msg.kinematics_jnt_eff
        self.kinematics_target_pos  = msg.kinematics_target_pos
        self.kinematics_target_quat = msg.kinematics_target_quat

        self.ft_force  = msg.ft_force
        self.ft_torque = msg.ft_torque

        self.vision_artag_pos  = msg.vision_artag_pos
        self.vision_artag_quat = msg.vision_artag_quat

        self.vision_change_centers_x = msg.vision_change_centers_x
        self.vision_change_centers_y = msg.vision_change_centers_y
        self.vision_change_centers_z = msg.vision_change_centers_z

        self.pps_skin_left  = msg.pps_skin_left
        self.pps_skin_right = msg.pps_skin_right

        self.fabric_skin_centers_x = msg.fabric_skin_centers_x
        self.fabric_skin_centers_y = msg.fabric_skin_centers_y
        self.fabric_skin_centers_z = msg.fabric_skin_centers_z
        self.fabric_skin_normals_x = msg.fabric_skin_normals_x
        self.fabric_skin_normals_y = msg.fabric_skin_normals_y
        self.fabric_skin_normals_z = msg.fabric_skin_normals_z
        self.fabric_skin_values_x  = msg.fabric_skin_values_x
        self.fabric_skin_values_y  = msg.fabric_skin_values_y
        self.fabric_skin_values_z  = msg.fabric_skin_values_z

        if self.enable_detector is False: return
        
        self.lock.acquire()
        newData = self.extractLocalFeature()
        if len(self.dataList) == 0:
            self.dataList = newData
        else:                
            #self.dataList = np.swapaxes(self.dataList, 0,1)
            for i in xrange(self.nEmissionDim):
                self.dataList[i] = np.hstack([ self.dataList[i], newData[i] ])
        self.lock.release()

                    
    def extractLocalFeature(self):

        data_dict = {}
        data_dict['timesList'] = [[0.]]
            
        # Unimoda feature - Audio --------------------------------------------
        if 'unimodal_audioPower' in self.handFeatures:
            ang_max, ang_min = util.getAngularSpatialRF(self.kinematics_ee_pos, self.rf_radius)
            if ang_min < self.audio_azimuth < ang_max:
                data_dict['audioPowerList'] = [self.audio_power]
            else:
                data_dict['audioPowerList'] = [0.0]

        # Unimodal feature - AudioWrist ---------------------------------------
        if 'unimodal_audioWristRMS' in self.handFeatures:
            data_dict['audioWristRMSList'] = [self.audio_wrist_rms]
            ## self.data_dict['audioWristMFCCList'].append(audio_mfcc)

        # Unimodal feature - Kinematics --------------------------------------
        if 'unimodal_kinVel' in self.handFeatures:
            print 'unimodal_kinVel not implemented'

        # Unimodal feature - Force -------------------------------------------
        if 'unimodal_ftForce' in self.handFeatures:
            data_dict['ftForceList']  = [np.array([self.ft_force]).T]
            data_dict['ftTorqueList'] = [np.array([self.ft_torque]).T]

        # Unimodal feature - pps -------------------------------------------
        if 'unimodal_ppsForce' in self.handFeatures:
            data_dict['ppsLeftList'] = [self.pps_skin_left]
            data_dict['ppsRightList'] = [self.pps_skin_right]
            data_dict['kinTargetPosList'] = [self.kinematics_target_pos]

        # Unimodal feature - vision change ------------------------------------
        if 'unimodal_visionChange' in self.handFeatures:
            vision_centers = np.array([self.vision_change_centers_x, self.vision_change_centers_y, self.vision_change_centers_z])
            data_dict['visionChangeMagList'] = [len(vision_centers[0])]
            print 'unimodal_visionChange may not be implemented properly'

        # Unimodal feature - fabric skin ------------------------------------
        if 'unimodal_fabricForce' in self.handFeatures:
            fabric_skin_values  = [self.fabric_skin_values_x, self.fabric_skin_values_y, self.fabric_skin_values_z]
            if not fabric_skin_values[0]:
                data_dict['fabricMagList'] = [0]
            else:
                data_dict['fabricMagList'] = [np.sum( np.linalg.norm(np.array(fabric_skin_values), axis=0) )]

        # Crossmodal feature - relative dist --------------------------
        if 'crossmodal_targetEEDist' in self.handFeatures:
            data_dict['kinEEPosList']     = [np.array([self.kinematics_ee_pos]).T]
            data_dict['kinTargetPosList'] = [np.array([self.kinematics_target_pos]).T]

        # Crossmodal feature - relative angle --------------------------
        if 'crossmodal_targetEEAng' in self.handFeatures:
            data_dict['kinEEQuatList'] = [np.array([self.kinematics_ee_quat]).T]
            data_dict['kinTargetQuatList'] = [np.array([self.kinematics_target_quat]).T]

        # Crossmodal feature - vision relative dist with main(first) vision target----
        if 'crossmodal_artagEEDist' in self.handFeatures:
            data_dict['visionArtagPosList'] = [np.array([self.vision_artag_pos]).T]

        # Crossmodal feature - vision relative angle --------------------------
        if 'crossmodal_artagEEAng' in self.handFeatures:
            data_dict['visionArtagPosList'] = [np.array([self.vision_artag_pos]).T]
            data_dict['visionArtagQuatList'] = [np.array([self.vision_artag_quat]).T]

        data, _ = dm.extractHandFeature(data_dict, self.handFeatures, scale=1.0, \
                                        param_dict = self.handFeatureParams)

                                        
        return data

    '''
    Reset parameters
    '''
    def reset(self):
        self.dataList = []
        self.enableDetector = False

    '''
    Run detector
    '''
    def run(self):
        rospy.loginfo("Start to run anomaly detection: " + self.task_name)

        rate = rospy.Rate(20) # 25Hz, nominally.
        while not rospy.is_shutdown():
            if self.enable_detector is False: continue            
            if self.dataList == [] or len(self.dataList[0][0]) < 10: continue

            self.lock.acquire()
            l_logp, l_post = self.ml.loglikelihoods(self.dataList, bPosterior=True, startIdx=4)
            ## l_logp, l_post = self.ml.loglikelihoods(self.tempdata, bPosterior=True, startIdx=4)
            self.lock.release()
            
            l_logp = l_logp[0]
            l_post = l_post[0]
            if l_logp == []: 
                rate.sleep()                
                continue
            ## print 'Shape of l_logp:', np.shape(l_logp), 'l_post:', np.shape(l_post)
            
            ll_classifier_test_X = [l_logp[-1]] + l_post[-1].tolist() 

            #?????                
            ## for i in xrange(len(ll_classifier_test_X)):
            if 'svm' in self.classifier_method:
                X = self.scaler.transform([ll_classifier_test_X])
            elif self.classifier_method == 'progress_time_cluster' or \
              self.classifier_method == 'fixed':
                X = ll_classifier_test_X
            else:
                print 'Invalid classifier method. Exiting.'
                exit()

            est_y = self.classifier.predict(X)
            if type(est_y) == list:
                est_y = est_y[0]

            print 'Estimated classification', est_y
            if est_y > 0.0:
                print '-'*15, 'Anomaly has occured!', '-'*15
                self.action_interruption_pub.publish(self.task_name+'_anomaly')
                self.task_interruption_pub.publish(self.task_name+'_anomaly')
                self.soundHandle.play(2)
                self.enable_detector = False
                self.reset()

            rate.sleep()

if __name__ == '__main__':

    import optparse
    p = optparse.OptionParser()
    p.add_option('--task', action='store', dest='task', type='string', default='scooping',
                 help='type the desired task name')
    opt, args = p.parse_args()

    if opt.task == 'scooping':
    
        subject_names     = ['Wonyoung', 'Tom', 'lin', 'Ashwin', 'Song', 'Henry2']
        task_name         = opt.task
        check_method      = 'svm' #'progress_time_cluster' # cssvm
        raw_data_path     = '/home/dpark/hrl_file_server/dpark_data/anomaly/RSS2016/'
        save_data_path    = '/home/dpark/hrl_file_server/dpark_data/anomaly/RSS2016/'+task_name+'_data/demo'

        handFeatures = ['unimodal_audioWristRMS',\
                        ## 'unimodal_kinVel',\
                        'unimodal_ftForce',\
                        'crossmodal_targetEEDist', \
                        'crossmodal_targetEEAng']

        data_param_dict= {'renew': False, 'rf_center': 'kinEEPos', 'local_range': 10.,\
                          'downSampleSize': 200, 'cut_data': [0,130], 'nNormalFold':4, 'nAbnormalFold':4,\
                          'handFeatures': handFeatures, 'lowVarDataRemv': False}
        AE_param_dict  = {'renew': False, 'switch': False, 'time_window': 4, 'filter': True, \
                          'layer_sizes':[64,32,16], 'learning_rate':1e-6, 'learning_rate_decay':1e-6, \
                          'momentum':1e-6, 'dampening':1e-6, 'lambda_reg':1e-6, \
                          'max_iteration':30000, 'min_loss':0.1, 'cuda':True, 'filter':True, 'filterDim':4}
        HMM_param_dict = {'renew': False, 'nState': 20, 'cov': 5.0, 'scale': 4.0}
        SVM_param_dict = {'renew': False, 'w_negative': 3.0, 'gamma': 0.3, 'cost': 6.0, \
                          'class_weight': 1.4e-3}
                          ## 'class_weight': 1.4e-3}

        param_dict = {'data_param': data_param_dict, 'AE': AE_param_dict, 'HMM': HMM_param_dict, \
                      'SVM': SVM_param_dict}

    elif opt.task == 'feeding':
        subjects       = ['Tom', 'lin', 'Ashwin', 'Song'] #'Wonyoung']
        task           = opt.task 
        check_method   = 'svm' #'progress_time_cluster' # cssvm
        save_data_path = '/home/dpark/hrl_file_server/dpark_data/anomaly/RSS2016/'+task+'_data'
        raw_data_path  = '/home/dpark/hrl_file_server/dpark_data/anomaly/RSS2016/'
        
        handFeatures    = ['unimodal_audioWristRMS', 'unimodal_ftForce', 'crossmodal_artagEEDist', \
                           'crossmodal_artagEEAng'] #'unimodal_audioPower'

        data_param_dict= {'renew': False, 'rf_center': 'kinEEPos', 'local_range': 10.,\
                          'downSampleSize': 200, 'cut_data': [0,170], \
                          'nNormalFold':4, 'nAbnormalFold':4,\
                          'feature_list': handFeatures, 'lowVarDataRemv': False}
        AE_param_dict  = {'renew': False, 'switch': False, 'time_window': 4, 'filter': True, \
                          'layer_sizes':[64,32,16], 'learning_rate':1e-6, 'learning_rate_decay':1e-6, \
                          'momentum':1e-6, 'dampening':1e-6, 'lambda_reg':1e-6, \
                          'max_iteration':30000, 'min_loss':0.1, 'cuda':True, 'filter':True, 'filterDim':4,\
                          'add_option': None, 'add_feature': feature_list} 
        HMM_param_dict = {'renew': False, 'nState': 25, 'cov': 5.0, 'scale': 4.0}
        SVM_param_dict = {'renew': False, 'w_negative': 1.3, 'gamma': 0.0103, 'cost': 1.0,\
                          'class_weight': 0.05}
                                 
        param_dict = {'data_param': data_param_dict, 'AE': AE_param_dict, 'HMM': HMM_param_dict, \
                      'SVM': SVM_param_dict}
        
                      
    else:
        sys.exit()


    ad = anomaly_detector(subject_names, task_name, check_method, raw_data_path, save_data_path, \
                          param_dict)
    ad.run()


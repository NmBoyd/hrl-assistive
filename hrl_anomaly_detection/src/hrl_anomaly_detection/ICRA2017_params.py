import os, sys
import numpy as np


def getParams(task, bDataRenew, bAERenew, bHMMRenew, dim, rf_center='kinEEPos',\
              local_range=10.0, bAESwitch=False, nPoints=None ):

    #---------------------------------------------------------------------------
    if task == 'scooping':
        raw_data_path, save_data_path, param_dict = getScooping(task, bDataRenew, \
                                                                bAERenew, bHMMRenew,\
                                                                rf_center, local_range,\
                                                                ae_swtch=bAESwitch, dim=dim,\
                                                                nPoints=nPoints)
        
    #---------------------------------------------------------------------------
    elif task == 'feeding':
        raw_data_path, save_data_path, param_dict = getFeeding(task, bDataRenew, \
                                                               bAERenew, bHMMRenew,\
                                                               rf_center, local_range,\
                                                               ae_swtch=bAESwitch, dim=dim,\
                                                               nPoints=nPoints)

    #---------------------------------------------------------------------------
    elif task == 'pushing':
        raw_data_path, save_data_path, param_dict = getPushing(task, bDataRenew, \
                                                               bAERenew, bHMMRenew,\
                                                               rf_center, local_range,\
                                                               ae_swtch=bAESwitch, dim=dim,\
                                                               nPoints=nPoints)

    else:
        print "Selected task name is not available."
        sys.exit()

    return raw_data_path, save_data_path, param_dict

def getScooping(task, data_renew, AE_renew, HMM_renew, rf_center='kinEEPos', local_range=10.0, \
                pre_train=False,\
                ae_swtch=False, dim=4, nPoints=None):

    if nPoints is None: nPoints = 20  

    if dim == 4:
        handFeatures = ['unimodal_ftForce',\
                        'crossmodal_targetEEDist', \
                        'crossmodal_targetEEAng', \
                        'unimodal_audioWristRMS']
        HMM_param_dict = {'renew': HMM_renew, 'nState': 25, 'cov': 3.566, 'scale': 1.0,
                          'add_logp_d': True}
        SVM_param_dict = {'renew': False, 'w_negative': 0.2, 'gamma': 0.01, 'cost': 15.0,\
                          'hmmosvm_nu': 0.00316,\
                          'hmmsvm_diag_w_negative': 0.85, 'hmmsvm_diag_cost': 12.5, \
                          'hmmsvm_diag_gamma': 0.01,\
                          'osvm_nu': 0.000215, 'raw_window_size': 10,\
                          'hmmsvm_dL_w_negative': 0.85, 'hmmsvm_dL_cost': 7.5, \
                          'hmmsvm_dL_gamma': 0.50749,
                          }
        
        ROC_param_dict = {'methods': [ 'svm' ],\
                          'update_list': ['svm'],\
                          'nPoints': nPoints,\
                          'hmmgp_param_range':np.linspace(0, -40.0, nPoints), \
                          'progress_param_range':np.linspace(0.0, -7., nPoints), \
                          'svm_param_range': np.logspace(-4, 1.2, nPoints),\
                          'change_param_range': np.logspace(-0.8, 1.0, nPoints)*-1.0,\
                          'fixed_param_range': np.logspace(0.0, 0.5, nPoints)*-1.0+1.3,\
                          'cssvm_param_range': np.logspace(-4.0, 2.0, nPoints),\
                          'hmmosvm_param_range': np.logspace(-4.0, 1.0, nPoints),\
                          'hmmsvm_diag_param_range': np.logspace(-4, 1.2, nPoints),\
                          'hmmsvm_dL_param_range': np.logspace(-4, 1.2, nPoints),\
                          'osvm_param_range': np.logspace(-5., 0.0, nPoints),\
                          'sgd_param_range': np.logspace(-4.0, 1.3, nPoints)}

        AD_param_dict = {'svm_w_positive': 1.0, 'sgd_w_positive': 1.0, 'sgd_n_iter': 20}
        
    elif dim == 3:
        handFeatures = ['unimodal_ftForce',\
                        'crossmodal_targetEEDist', \
                        'crossmodal_targetEEAng']
        HMM_param_dict = {'renew': HMM_renew, 'nState': 25, 'cov': 3.566, 'scale': 3.0,\
                          'add_logp_d': True}
        SVM_param_dict = {'renew': False, 'w_negative': 0.825, 'gamma': 3.16, 'cost': 4.0,\
                          'hmmosvm_nu': 0.00316,\
                          'hmmsvm_diag_w_negative': 0.85, 'hmmsvm_diag_cost': 12.5, \
                          'hmmsvm_diag_gamma': 0.01}

        ROC_param_dict = {'methods': [ 'fixed', 'progress', 'svm', 'hmmosvm'],\
                          'update_list': ['hmmosvm'],\
                          'nPoints': nPoints,\
                          'progress_param_range':np.linspace(-0.8, -5., nPoints), \
                          'svm_param_range': np.logspace(-2.5, 0, nPoints),\
                          'fixed_param_range': np.linspace(0.0, -1.5, nPoints),\
                          'cssvm_param_range': np.logspace(-4.0, 2.0, nPoints),\
                          ## 'svm_param_range': np.logspace(-4, 1.2, nPoints),\
                          'hmmosvm_param_range': np.logspace(-4.0, 1.0, nPoints),\
                          'osvm_param_range': np.linspace(0.1, 2.0, nPoints),\
                          'sgd_param_range': np.logspace(-4, 1.2, nPoints)}        
        AD_param_dict = {'svm_w_positive': 0.1, 'sgd_w_positive': 1.0}
        
    elif dim == 2:
        handFeatures = ['unimodal_ftForce',\
                        'crossmodal_targetEEDist' ]
        HMM_param_dict = {'renew': HMM_renew, 'nState': 25, 'cov': 1.4, 'scale': 3.0,\
                          'add_logp_d': True}
        SVM_param_dict = {'renew': False, 'w_negative': 3.5, 'gamma': 0.0147, 'cost': 3.0,\
                          'hmmosvm_nu': 0.00316}

        ROC_param_dict = {'methods': [ 'fixed', 'progress', 'svm', 'hmmosvm'],\
                          'update_list': ['hmmosvm'],\
                          'nPoints': nPoints,\
                          'progress_param_range':np.linspace(-0.8, -8., nPoints), \
                          'svm_param_range': np.logspace(-1.5, 1, nPoints),\
                          'fixed_param_range': np.linspace(0.2, -3.0, nPoints),\
                          'cssvm_param_range': np.logspace(-4.0, 2.0, nPoints),\
                          ## 'svm_param_range': np.logspace(-4, 1.2, nPoints),\
                          'hmmosvm_param_range': np.logspace(-4.0, 1.5, nPoints),\
                          'osvm_param_range': np.linspace(0.1, 2.0, nPoints),\
                          'sgd_param_range': np.logspace(-4, 1.2, nPoints)}        
        AD_param_dict = {'svm_w_positive': 1.0, 'sgd_w_positive': 1.0}
        
    rawFeatures = ['relativePose_target_EE', \
                   'wristAudio', \
                   'ft' ]                                
    modality_list = ['kinematics', 'audioWrist', 'ft', \
                     'pps']
    raw_data_path  = os.path.expanduser('~')+'/hrl_file_server/dpark_data/anomaly/ICRA2017/'

    AE_param_dict  = {'renew': AE_renew, 'switch': ae_swtch, 'method': 'ae', 'time_window': 4,  \
                      'layer_sizes':[], 'learning_rate':1e-4, \
                      'learning_rate_decay':1e-6, \
                      'momentum':1e-6, 'dampening':1e-6, 'lambda_reg':1e-6, \
                      'max_iteration':100000, 'min_loss':0.01, 'cuda':True, \
                      'pca_gamma': 1.0,\
                      'filter':False, 'filterDim':4, \
                      'nAugment': 1, \
                      'add_option': None, 'rawFeatures': rawFeatures,\
                      'add_noise_option': [], 'preTrainModel': None}

    data_param_dict= {'renew': data_renew, 'rf_center': rf_center, 'local_range': local_range,\
                      'downSampleSize': 200, 'cut_data': None, \
                      'nNormalFold':3, 'nAbnormalFold':3,\
                      'handFeatures': handFeatures, 'lowVarDataRemv': False,\
                      'handFeatures_noise': True, 'max_time': None}

    save_data_path = os.path.expanduser('~')+\
      '/hrl_file_server/dpark_data/anomaly/ICRA2017/'+task+'_data/'+\
      str(data_param_dict['downSampleSize'])+'_'+str(dim)
      
    param_dict = {'data_param': data_param_dict, 'AE': AE_param_dict, 'HMM': HMM_param_dict, \
                  'SVM': SVM_param_dict, 'ROC': ROC_param_dict, 'AD': AD_param_dict}
      
    return raw_data_path, save_data_path, param_dict


def getFeeding(task, data_renew, AE_renew, HMM_renew, rf_center='kinEEPos',local_range=10.0, \
               ae_swtch=False, dim=4, nPoints=None):

    if nPoints is None: nPoints = 20 

    if dim == 4:

        handFeatures = ['unimodal_audioWristRMS', 'unimodal_ftForceZ', \
                        'crossmodal_landmarkEEDist', 'crossmodal_landmarkEEAng']
        HMM_param_dict = {'renew': HMM_renew, 'nState': 25, 'cov': 9., 'scale': 9.,\
                          'add_logp_d': False}
        SVM_param_dict = {'renew': False, 'w_negative': 1.52, 'gamma': 5.0, 'cost': 1.0,\
                          'hmmosvm_nu': 0.000316,\
                          'osvm_nu': 0.000359,\
                          'hmmsvm_diag_w_negative': 0.2, 'hmmsvm_diag_cost': 15.0, \
                          'hmmsvm_diag_gamma': 2.0,\
                          'raw_window_size': 10,\
                          'hmmsvm_dL_w_negative': 0.525, 'hmmsvm_dL_cost': 5.0, \
                          'hmmsvm_dL_gamma': 4.0,\
                          'bpsvm_cost': 12.5,\
                          'bpsvm_gamma': 0.01, \
                          'bpsvm_w_negative': 0.2,\
                          'logp_offset': 0,\
                          'sgd_gamma':0.32, 'sgd_w_negative':2.5
                          }
            
            #, 'bpsvm'      , 'osvm'
            ## 'progress_param_range': -np.logspace(-1, 0.5, nPoints)+0.1,\
        ROC_param_dict = {'methods': ['hmmgp', 'progress', 'fixed', 'change'],\
                          'update_list': [],\
                          'nPoints': nPoints,\
                          'm2o': {'gp_nSubsample': 20, 'alpha_coeff': 0.15, 'hmm_scale': 9.0, 'hmm_cov': 9.0,\
                                  'noise_max': 0.0 },\
                          'o2o': {'gp_nSubsample': 40, 'alpha_coeff': 0.05, 'hmm_scale': 3.0, 'hmm_cov': 1.0,\
                                  'noise_max': 0.05 },\
                          'progress_param_range': -np.logspace(0, 2.5, nPoints),\
                          'kmean_param_range': -np.logspace(0, 3.0, nPoints),\
                          'svm_param_range': np.logspace(-0.4, 0.5, nPoints),\
                          'hmmgp_param_range':np.logspace(-1, 3.5, nPoints)*-1.0+0.5, \
                          'hmmsvm_diag_param_range': np.logspace(-4, 1.2, nPoints),\
                          'hmmsvm_dL_param_range': np.logspace(-4, 1.2, nPoints),\
                          'hmmosvm_param_range': np.logspace(-4.0, 1.0, nPoints),\
                          'change_param_range': np.logspace(0.0, 2.6, nPoints)*-1.0,\
                          'osvm_param_range': np.logspace(-5., 0.0, nPoints),\
                          'bpsvm_param_range': np.logspace(-2.2, 0.5, nPoints),\
                          'fixed_param_range': np.linspace(0.15, -0.5, nPoints),\
                          'cssvm_param_range': np.logspace(0.0, 2.0, nPoints),\
                          'sgd_param_range': np.logspace(-1, 1., nPoints)}

        AD_param_dict = {'svm_w_positive': 1.0, 'sgd_w_positive': 1.0, 'sgd_n_iter': 20}
                          
    elif dim == 3:

        handFeatures = ['unimodal_ftForce', \
                        'crossmodal_landmarkEEDist', 'crossmodal_landmarkEEAng']
        HMM_param_dict = {'renew': HMM_renew, 'nState': 25, 'cov': 3.5, 'scale': 2.555,\
                          'add_logp_d': True}
        SVM_param_dict = {'renew': False, 'w_negative': 1.55, 'gamma': 3.911, 'cost': 1.0,\
                          'hmmosvm_nu': 0.001,\
                          'hmmsvm_bpsvm_cost': 12.5,\
                          'hmmsvm_bpsvm_gamma': 0.507, \
                          'hmmsvm_bpsvm_w_negative': 0.2
                          }
                          
        ROC_param_dict = {'methods': ['progress', 'fixed', 'svm', 'hmmosvm'],\
                          'update_list': ['hmmosvm'],\
                          'nPoints': nPoints,\
                          'progress_param_range': -np.logspace(0., 1.5, nPoints),\
                          'svm_param_range': np.logspace(-0.8, 2.5, nPoints),\
                          'bpsvm_param_range': np.logspace(-2, 0, nPoints),\
                          'hmmosvm_param_range': np.logspace(-4.5, 0.5, nPoints),\
                          'fixed_param_range': np.linspace(0.1, -0.1, nPoints),\
                          'cssvm_param_range': np.logspace(0.0, 2.0, nPoints) }

        AD_param_dict = {'svm_w_positive': 1.0, 'sgd_w_positive': 1.0}
                          
    elif dim == 2:

        ## handFeatures = ['unimodal_ftForce', \
        ##                 'crossmodal_landmarkEEDist']
        handFeatures = ['unimodal_audioWristRMS', 'unimodal_ftForce']
        HMM_param_dict = {'renew': HMM_renew, 'nState': 25, 'cov': 3.5, 'scale': 13.444,\
                          'add_logp_d': True}
        ## HMM_param_dict = {'renew': HMM_renew, 'nState': 25, 'cov': 6.0, 'scale': 3.0}
        SVM_param_dict = {'renew': False, 'w_negative': 5.0, 'gamma': 2.049, 'cost': 1.75,\
                          'hmmosvm_nu': 0.0001,\
                          'hmmsvm_bpsvm_cost': 15.0,\
                          'hmmsvm_bpsvm_gamma': 0.01, \
                          'hmmsvm_bpsvm_w_negative': 1.5
                          }

        ROC_param_dict = {'methods': ['progress', 'svm','fixed', 'hmmosvm'],\
                          'update_list': ['hmmosvm'],\
                          'nPoints': nPoints,\
                          'progress_param_range': -np.logspace(-0.3, 1.8, nPoints)+0.1,\
                          'svm_param_range': np.logspace(-2.5, 0.7, nPoints),\
                          'hmmosvm_param_range': np.logspace(-4.0, 0.5, nPoints),\
                          'fixed_param_range': np.linspace(0.5, -0.0, nPoints),\
                          'bpsvm_param_range': np.logspace(-2, 0, nPoints),\
                          'cssvm_param_range': np.logspace(0.0, 2.0, nPoints) }

        AD_param_dict = {'svm_w_positive': 1.0, 'sgd_w_positive': 1.0}

        
    rawFeatures = ['relativePose_target_EE', \
                   'wristAudio', \
                   'ft',\
                   'relativePose_landmark_EE']

    modality_list   = ['ft' ,'kinematics', 'audioWrist', 'vision_landmark']
    raw_data_path  = os.path.expanduser('~')+'/hrl_file_server/dpark_data/anomaly/ICRA2017/'

    AE_param_dict  = {'renew': AE_renew, 'switch': False, 'time_window': 4, \
                      'layer_sizes':[64,dim], 'learning_rate':1e-6, 'learning_rate_decay':1e-6, \
                      'momentum':1e-6, 'dampening':1e-6, 'lambda_reg':1e-6, \
                      'max_iteration':30000, 'min_loss':0.1, 'cuda':True, \
                      'filter':True, 'filterDim':4,\
                      'add_option': None, 'rawFeatures': rawFeatures,\
                      'add_noise_option': [], 'preTrainModel': None}                      

    data_param_dict= {'renew': data_renew, 'rf_center': rf_center, 'local_range': local_range,\
                      'downSampleSize': 200, 'cut_data': None, \
                      'nNormalFold':2, 'nAbnormalFold':2,\
                      'handFeatures': handFeatures, 'lowVarDataRemv': False,\
                      'handFeatures_noise': True, 'max_time': 7.0}

    save_data_path = os.path.expanduser('~')+\
      '/hrl_file_server/dpark_data/anomaly/ICRA2017/'+task+'_data/'+\
      str(data_param_dict['downSampleSize'])+'_'+str(dim)

    param_dict = {'data_param': data_param_dict, 'AE': AE_param_dict, 'HMM': HMM_param_dict, \
                  'SVM': SVM_param_dict, 'ROC': ROC_param_dict, 'AD': AD_param_dict}

    return raw_data_path, save_data_path, param_dict


def getPushing(task, data_renew, AE_renew, HMM_renew, rf_center,local_range, pre_train=False, \
               ae_swtch=False, dim=3, nPoints=None):
    if nPoints is None: nPoints = 20

    if dim == 5:
        handFeatures = ['unimodal_ftForce',\
                        'crossmodal_artagEEDist',\
                        'crossmodal_artagEEAng',\
                        'crossmodal_subArtagEEDist',\
                        'unimodal_audioWristRMS'] #'unimodal_audioPower', ,
        HMM_param_dict = {'renew': HMM_renew, 'nState': 25, 'cov': 1.788, 'scale': 10.0, \
                          'add_logp_d': False}
        SVM_param_dict = {'renew': False, 'w_negative': 0.525, 'gamma': 0.0316, 'cost': 4.0,\
                          'hmmosvm_nu': 0.00316}

        ROC_param_dict = {'methods': ['fixed', 'progress', 'kmean'],\
                          'update_list': [ 'hmmgp', 'fixed' ],\
                          'nPoints': nPoints,\
                          'hmmgp_param_range':np.logspace(-1, 2.0, nPoints)*-1.0, \
                          'progress_param_range':np.logspace(-1.0, 1.2, nPoints)*-1.0 +1., \
                          'kmean_param_range':np.logspace(-1.1, 1.0, nPoints)*-1.0 -0.5, \
                          'fixed_param_range': np.linspace(-7.0, 0.0, nPoints),\
                          'svm_param_range': np.logspace(-2.5, -0.276, nPoints),\
                          'cssvm_param_range': np.logspace(-4.0, 2.0, nPoints),\
                          'hmmosvm_param_range': np.logspace(-4.0, 1.8, nPoints),\
                          'change_param_range': np.linspace(-1.0, -20.0, nPoints),\
                          'osvm_param_range': np.logspace(-5, 0, nPoints),\
                          'sgd_param_range': np.logspace(-4, 1.2, nPoints)}        
        
    elif dim == 4:
        handFeatures = ['unimodal_ftForce',\
                        'crossmodal_artagEEDist',\
                        'crossmodal_subArtagEEDist',\
                        'unimodal_audioWristRMS'] #'unimodal_audioPower', ,
        HMM_param_dict = {'renew': HMM_renew, 'nState': 25, 'cov': 5.6688, 'scale': 5., \
                          'add_logp_d': False}
        SVM_param_dict = {'renew': False, 'w_negative': 0.85, 'gamma': 0.001, 'cost': 12.5,\
                          'sgd_gamma':0.32, 'sgd_w_negative':2.5,\
                          'hmmosvm_nu': 0.00316,
                          'hmmsvm_diag_w_negative': 1.5, \
                          'hmmsvm_diag_cost': 10.0, \
                          'hmmsvm_diag_gamma': 0.01,\
                          'osvm_nu': 0.000359,
                          'hmmsvm_dL_w_negative': 1.5, \
                          'hmmsvm_dL_cost': 7.5, \
                          'hmmsvm_dL_gamma': 0.01,\
                          'hmmsvm_no_dL_w_negative': 3.25, \
                          'hmmsvm_no_dL_cost': 3.75, \
                          'hmmsvm_no_dL_gamma': 0.0133,\
                          'bpsvm_cost': 5.0,\
                          'bpsvm_gamma': 0.507, \
                          'bpsvm_w_negative': 1.5,\
                          'progress_svm_w_negative': 1.5, 'progress_svm_cost': 15.0, \
                          'progress_svm_gamma': 0.01 }

        # 'svm' , 'hmmosvm', 'hmmsvm_diag', 'hmmsvm_dL', 'hmmsvm_no_dL', , 
        ROC_param_dict = {'methods': [ ],\
                          'update_list': [ ],\
                          'nPoints': nPoints,\
                          'm2o': {'gp_nSubsample': 20, 'alpha_coeff': 0.15, 'hmm_scale': 9.0, 'hmm_cov': 9.0,\
                                  'noise_max': 0.0},\
                          'o2o': {'gp_nSubsample': 40, 'alpha_coeff': 0.05, 'hmm_scale': 9.0, 'hmm_cov': 9.0,\
                                  'noise_max': 0.2},\
                          'progress_param_range':np.logspace(0.1, 1.3, nPoints)*-1.0, \
                          'progress_diag_param_range':np.logspace(0, 1.2, nPoints)*-1.0, \
                          'kmean_param_range':np.logspace(-1.1, 1.2, nPoints)*-1.0 -1., \
                          'progress_state_param_range':np.logspace(-0.4, 3.3, nPoints)*-1.0+0.4, \
                          'progress_svm_param_range': np.linspace(0.005, 6.0, nPoints),\
                          'progress_osvm_param_range': np.logspace(-6.0, 1.0, nPoints),\
                          'hmmgp_param_range':np.logspace(0.3, 3.0, nPoints)*-1.0, \
                          'fixed_param_range': np.linspace(-1.1, 0.171, nPoints),\
                          'change_param_range': np.logspace(0.2, 1.3, nPoints)*-1.0,\
                          'osvm_param_range': np.logspace(-6, 0.0, nPoints),\
                          'svm_param_range': np.logspace(-1.236, 0.7, nPoints),\
                          'bpsvm_param_range': np.logspace(-3., 0.4, nPoints),\
                          'hmmsvm_diag_param_range': np.logspace(-1.85, 0.486, nPoints),\
                          'hmmsvm_dL_param_range': np.logspace(-3.0, 0.7, nPoints),\
                          'hmmsvm_no_dL_param_range': np.logspace(-1.346, 0.8, nPoints),\
                          'hmmosvm_param_range': np.logspace(-4.0, 1.5, nPoints),\
                          'cssvm_param_range': np.logspace(-4.0, 2.0, nPoints),
                          'sgd_param_range': np.logspace(-4, 1.2, nPoints) }        
        
    elif dim == 3:
        handFeatures = ['unimodal_ftForce',\
                        'crossmodal_artagEEDist',\
                        'unimodal_audioWristRMS'] #'unimodal_audioPower', ,
        HMM_param_dict = {'renew': HMM_renew, 'nState': 25, 'cov': 1.0, 'scale': 8.,\
                          'add_logp_d': False}
        SVM_param_dict = {'renew': False, 'w_negative': 1.175, 'gamma': 0.0063, 'cost':7.5,\
                          'hmmosvm_nu': 0.001}
        
        ROC_param_dict = {'methods': ['fixed', 'progress', 'kmean'],\
                          'update_list': [ 'progress' ],\
                          'nPoints': nPoints,\
                          'hmmgp_param_range':np.logspace(-0.6, 1.8, nPoints)*-1.0, \
                          'progress_param_range':np.logspace(-1, 1.3, nPoints)*-1.0 + 1.0, \
                          'kmean_param_range':np.logspace(-1.1, 1.0, nPoints)*-1.0 -0.5, \
                          'svm_param_range': np.logspace(-1.22, 0.2, nPoints),\
                          'fixed_param_range': np.linspace(0.3, -5.0, nPoints),\
                          'cssvm_param_range': np.logspace(-4.0, 2.0, nPoints),\
                          'hmmosvm_param_range': np.logspace(-3.0, 0.3, nPoints),\
                          'change_param_range': np.linspace(-1.5, -20.0, nPoints),\
                          'osvm_param_range': np.logspace(-5, 0., nPoints)}        
    elif dim == 2:
        handFeatures = ['unimodal_ftForce',\
                        'unimodal_audioWristRMS'] #'unimodal_audioPower', ,
        HMM_param_dict = {'renew': HMM_renew, 'nState': 25, 'cov': 0.3, 'scale': 10.0,\
                          'add_logp_d': False}
        SVM_param_dict = {'renew': False, 'w_negative': 1.584, 'gamma': 6.0, 'cost': 2.1666,\
                          'hmmosvm_nu': 0.001,
                          'hmmsvm_diag_w_negative': 1.5, 'hmmsvm_diag_cost': 12.5, \
                          'hmmsvm_diag_gamma': 0.01}
                          

        ROC_param_dict = {'methods': [ ],\
                          'update_list': [ 'kmean' , 'hmmgp'],\
                          'nPoints': nPoints,\
                          'hmmgp_param_range':np.linspace(3., -35.0, nPoints), \
                          'progress_param_range':np.linspace(0.0, -9.0, nPoints), \
                          'kmean_param_range':np.logspace(-0.3, 1.0, nPoints)*-1.0 , \
                          'svm_param_range': np.logspace(-3.0, -0.3458, nPoints),\
                          'fixed_param_range': np.linspace(1.0, -2.0, nPoints),\
                          'cssvm_param_range': np.logspace(-4.0, 2.0, nPoints),\
                          'hmmosvm_param_range': np.logspace(-6.0, 0.3, nPoints),\
                          'osvm_param_range': np.logspace(-5, 0, nPoints),\
                          'change_param_range': np.linspace(-1.0, -10.0, nPoints),\
                          'hmmsvm_diag_param_range': np.logspace(-4, 1.2, nPoints)}        
        
    rawFeatures = ['relativePose_artag_EE', \
                   'wristAudio', \
                   'ft' ]                                
    modality_list   = ['kinematics', 'audio', 'ft', 'vision_artag'] # raw plot
    raw_data_path  = '/home/dpark/hrl_file_server/dpark_data/anomaly/ICRA2017/'

    AE_param_dict  = {'renew': AE_renew, 'switch': ae_swtch, 'method': 'ae', 'time_window': 4,  \
                      'layer_sizes':[], 'learning_rate':1e-4, \
                      'learning_rate_decay':1e-6, \
                      'momentum':1e-6, 'dampening':1e-6, 'lambda_reg':1e-6, \
                      'max_iteration':50000, 'min_loss':0.01, 'cuda':True, \
                      'pca_gamma': 1.0,\
                      'filter':False, 'filterDim':4, \
                      'nAugment': 1, \
                      'add_option': None, 'rawFeatures': rawFeatures,\
                      'add_noise_option': [], 'preTrainModel': None}

    data_param_dict= {'renew': data_renew, 'rf_center': rf_center, 'local_range': local_range,\
                      'downSampleSize': 200, 'cut_data': None, \
                      'nNormalFold':3, 'nAbnormalFold':3,\
                      'handFeatures': handFeatures, 'lowVarDataRemv': False,\
                      'handFeatures_noise': True, 'max_time': None}

    data_param_dict['downSampleSize'] = 200
    save_data_path = os.path.expanduser('~')+\
      '/hrl_file_server/dpark_data/anomaly/ICRA2017/'+task+'_data/'+\
      str(data_param_dict['downSampleSize'])+'_'+str(dim)
    AE_param_dict['layer_sizes'] = [64,dim]
    AE_param_dict['preTrainModel'] = os.path.join(save_data_path, 'ae_pretrain_model_'+str(dim)+'.pkl')

    param_dict = {'data_param': data_param_dict, 'AE': AE_param_dict, 'HMM': HMM_param_dict, \
                  'SVM': SVM_param_dict, 'ROC': ROC_param_dict}

    return raw_data_path, save_data_path, param_dict

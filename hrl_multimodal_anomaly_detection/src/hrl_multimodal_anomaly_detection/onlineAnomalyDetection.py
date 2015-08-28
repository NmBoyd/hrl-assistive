#!/usr/bin/env python

__author__ = 'zerickson'

import time
import rospy
import pyaudio
from threading import Thread
import matplotlib.pyplot as plt
import hmm.icra2015Batch as onlineHMM
from audio.tool_audio_slim import tool_audio_slim
from hmm.util import *

try :
    import sensor_msgs.point_cloud2 as pc2
except:
    import vision.point_cloud2 as pc2
from geometry_msgs.msg import PoseStamped, WrenchStamped, Point
from std_msgs.msg import String
from visualization_msgs.msg import Marker
from roslib import message

import roslib
roslib.load_manifest('hrl_multimodal_anomaly_detection')
import tf
import image_geometry
from cv_bridge import CvBridge, CvBridgeError
from hrl_multimodal_anomaly_detection.msg import Circle, Rectangle, ImageFeatures

class onlineAnomalyDetection(Thread):
    MAX_INT = 32768.0
    CHUNK   = 1024 # frame per buffer
    RATE    = 48000 # sampling rate
    UNIT_SAMPLE_TIME = 1.0 / float(RATE)
    CHANNEL = 2 # number of channels
    FORMAT  = pyaudio.paInt16

    def __init__(self, targetFrame=None, tfListener=None, isScooping=True):
        super(onlineAnomalyDetection, self).__init__()
        self.daemon = True
        self.cancelled = False
        self.isRunning = False

        # Predefined settings
        self.downSampleSize = 100 #200
        self.scale = 1.0 #10
        self.nState = 10 #20
        self.cov_mult = 1.0
        self.cutting_ratio  = [0.0, 1.0] #[0.0, 0.7]
        self.isScooping = isScooping
        if self.isScooping: self.ml_thres_pkl='ml_scooping_thres.pkl'
        else: self.ml_thres_pkl='ml_feeding_thres.pkl'

        print 'is scooping:', self.isScooping

        self.publisher = rospy.Publisher('visualization_marker', Marker)
        self.interruptPublisher = rospy.Publisher('InterruptAction', String)
        self.targetFrame = targetFrame

        # Data logging
        self.updateNumber = 0
        self.lastUpdateNumber = 0
        self.init_time = rospy.get_time()

        if tfListener is None:
            self.transformer = tf.TransformListener()
        else:
            self.transformer = tfListener

        # Gripper
        self.lGripperPosition = None
        self.lGripperRotation = None
        self.mic = None
        self.grips = []
        # Spoon
        self.spoon = None

        # FT sensor
        self.force = None
        self.torque = None

        self.audioTool = tool_audio_slim()

        ## self.soundHandle = SoundClient()

        saveDataPath = '/home/dpark/git/hrl-assistive/hrl_multimodal_anomaly_detection/src/hrl_multimodal_anomaly_detection/hmm/batchDataFiles/%s_%d_%d_%d_%d.pkl'
        # Setup HMM to perform online anomaly detection
        self.hmm, self.minVals, self.maxVals, self.minThresholds \
        = onlineHMM.iteration(downSampleSize=self.downSampleSize,
                              scale=self.scale, nState=self.nState,
                              cov_mult=self.cov_mult, verbose=False,
                              isScooping=self.isScooping, use_pkl=False,
                              train_cutting_ratio=self.cutting_ratio,
                              findThresholds=True, ml_pkl=self.ml_thres_pkl,
                              savedDataFile=saveDataPath % (('scooping' if self.isScooping else 'feeding'),
                                            self.downSampleSize, self.scale, self.nState, int(self.cov_mult)))

        print 'Threshold:', self.minThresholds
        
        self.forces = []
        self.distances = []
        self.angles = []
        self.audios = []
        self.times = []
        self.anomalyOccured = False

        self.forceSub = rospy.Subscriber('/netft_data', WrenchStamped, self.forceCallback)
        print 'Connected to FT sensor'

        self.objectCenter = None
        self.objectCenterSub = rospy.Subscriber('/ar_track_alvar/bowl_cen_pose' if isScooping else '/ar_track_alvar/mouth_pose', PoseStamped, self.objectCenterCallback)
        print 'Connected to center of object publisher'

    def reset(self):
        self.isRunning = True
        self.forces = []
        self.distances = []
        self.angles = []
        self.audios = []
        self.times = []
        self.anomalyOccured = False
        self.updateNumber = 0
        self.lastUpdateNumber = 0
        self.init_time = rospy.get_time()
        self.lGripperPosition = None
        self.lGripperRotation = None
        self.mic = None
        self.grips = []
        self.spoon = None
        self.force = None
        self.torque = None
        self.objectCenter = None
        self.audioTool.begin()

    def run(self):
        """Overloaded Thread.run, runs the update
        method once per every xx milliseconds."""
        # rate = rospy.Rate(1000) # 25Hz, nominally.
        while not self.cancelled:
            if self.isRunning and self.updateNumber > self.lastUpdateNumber and self.objectCenter is not None:
                self.lastUpdateNumber = self.updateNumber
                self.processData()
                if not self.anomalyOccured and len(self.forces) > 15:
                    # Perform anomaly detection
                    (anomaly, error) = self.hmm.anomaly_check(self.forces, self.distances, self.angles, self.audios, self.minThresholds)
                    print 'Anomaly error:', error
                    if anomaly:
                        if self.isScooping:
                            self.interruptPublisher.publish('Interrupt')
                        else:
                            self.interruptPublisher.publish('InterruptHead')
                        self.anomalyOccured = True
                        print 'AHH!! There is an anomaly at time stamp', rospy.get_time() - self.init_time, (anomaly, error)
                        # for modality in [[self.forces] + self.forcesList[:5], [self.distances] + self.distancesList[:5], [self.angles] + self.anglesList[:5], [self.pdfs] + self.pdfList[:5]]:
                        #     for index, (modal, times) in enumerate(zip(modality, [self.times] + self.timesList[:5])):
                        #         plt.plot(times, modal, label='%d' % index)
                        #     plt.legend()
                        #     plt.show()
            # rate.sleep()

    def cancel(self):
        self.isRunning = False
        self.audioTool.reset()
        # self.forceSub.unregister()
        # self.objectCenterSub.unregister()
        # self.publisher.unregister()
        rospy.sleep(1.0)
                
    def processData(self):
        # Find nearest time stamp from training data
        # timeStamp = rospy.get_time() - self.init_time
        # index = np.abs(self.times - timeStamp).argmin()

        self.transposeGripper()

        # Use magnitude of forces
        force = np.linalg.norm(self.force)

        # Determine distance between mic and center of object
        distance = np.linalg.norm(self.mic - self.objectCenter)
        # Find angle between gripper-object vector and gripper-spoon vector
        micSpoonVector = self.spoon - self.mic
        micObjectVector = self.objectCenter - self.mic
        angle = np.arccos(np.dot(micSpoonVector, micObjectVector) / (np.linalg.norm(micSpoonVector) * np.linalg.norm(micObjectVector)))

        # Process either visual or audio data depending on which we're using
        audio = self.audioTool.readData()
        if audio is None:
            print 'Audio is None'
            return
        audio = get_rms(audio)
        # print 'Audio:', audio

        # Scale data
        force = self.scaling(force, minVal=self.minVals[0], maxVal=self.maxVals[0], scale=self.scale)
        distance = self.scaling(distance, minVal=self.minVals[1], maxVal=self.maxVals[1], scale=self.scale)
        audio = self.scaling(audio, minVal=self.minVals[3], maxVal=self.maxVals[3], scale=self.scale)
        angle = self.scaling(angle, minVal=self.minVals[2], maxVal=self.maxVals[2], scale=self.scale)

        self.forces.append(force)
        self.distances.append(distance)
        self.angles.append(angle)
        self.audios.append(audio)

    @staticmethod
    def scaling(x, minVal, maxVal, scale=1.0):
        return (x - minVal) / (maxVal - minVal) * scale

    def forceCallback(self, msg):
        self.force = np.array([msg.wrench.force.x, msg.wrench.force.y, msg.wrench.force.z])
        self.torque = np.array([msg.wrench.torque.x, msg.wrench.torque.y, msg.wrench.torque.z])
        self.updateNumber += 1

    def objectCenterCallback(self, msg):
        self.objectCenter = np.array([msg.pose.position.x, msg.pose.position.y, msg.pose.position.z])

    def transposeGripper(self):
        # Transpose gripper position to camera frame
        self.transformer.waitForTransform(self.targetFrame, '/l_gripper_tool_frame', rospy.Time(0), rospy.Duration(5))
        try :
            self.lGripperPosition, self.lGripperRotation = self.transformer.lookupTransform(self.targetFrame, '/l_gripper_tool_frame', rospy.Time(0))
            transMatrix = np.dot(tf.transformations.translation_matrix(self.lGripperPosition), tf.transformations.quaternion_matrix(self.lGripperRotation))
        except tf.ExtrapolationException:
            print 'Transpose of gripper failed!'
            return

        # Use a buffer of gripper positions
        if len(self.grips) >= 2:
            lGripperTransposeMatrix = self.grips[-2]
        else:
            lGripperTransposeMatrix = transMatrix
        self.grips.append(transMatrix)

        # Determine location of mic
        mic = [0.12, -0.02, 0]
        # print 'Mic before', mic
        self.mic = np.dot(lGripperTransposeMatrix, np.array([mic[0], mic[1], mic[2], 1.0]))[:3]
        # print 'Mic after', self.mic
        # Determine location of spoon
        spoon3D = [0.22, -0.050, 0]
        self.spoon = np.dot(lGripperTransposeMatrix, np.array([spoon3D[0], spoon3D[1], spoon3D[2], 1.0]))[:3]

    def find_input_device(self):
        device_index = None
        for i in range(self.p.get_device_count()):
            devinfo = self.p.get_device_info_by_index(i)
            print('Device %d: %s'%(i, devinfo['name']))

            for keyword in ['mic', 'input', 'icicle']:
                if keyword in devinfo['name'].lower():
                    print('Found an input: device %d - %s'%(i, devinfo['name']))
                    device_index = i
                    return device_index

        if device_index is None:
            print('No preferred input found; using default input device.')

        return device_index

    def publishPoints(self, name, points, size=0.01, r=0.0, g=0.0, b=0.0, a=1.0):
        marker = Marker()
        marker.header.frame_id = '/torso_lift_link'
        marker.ns = name
        marker.type = marker.POINTS
        marker.action = marker.ADD
        marker.scale.x = size
        marker.scale.y = size
        marker.color.a = a
        marker.color.r = r
        marker.color.g = g
        marker.color.b = b
        for point in points:
            p = Point()
            # print point
            p.x, p.y, p.z = point
            marker.points.append(p)
        self.publisher.publish(marker)



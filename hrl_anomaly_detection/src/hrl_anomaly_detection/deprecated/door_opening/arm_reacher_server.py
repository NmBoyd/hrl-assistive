#!/usr/bin/env python  

import roslib; roslib.load_manifest('sandbox_dpark_darpa_m3')
roslib.load_manifest('hrl_anomaly_detection')
import rospy
import numpy as np, math
import time

from hrl_srvs.srv import None_Bool, None_BoolResponse
from geometry_msgs.msg import PoseStamped, Point, Quaternion
from sandbox_dpark_darpa_m3.lib.hrl_mpc_base import mpcBaseAction


class armReachAction(mpcBaseAction):
    def __init__(self, d_robot, controller, arm='l'):

        mpcBaseAction.__init__(self, d_robot, controller, arm)
        
        # service request
        self.reach_service = rospy.Service('/door_opening/arm_reach_enable', None_Bool, self.start_cb)

        
    def start_cb(self, req):

        # Run manipulation tasks
        if self.run():
            return None_BoolResponse(True)
        else:
            return None_BoolResponse(False)

        
    def run(self):

        self.setOrientationControl()

        pos  = Point()
        quat = Quaternion()

        #going to home with arm curled high near left shoulder:
        (pos.x, pos.y, pos.z) = (0.801033944729, -0.101276517595, 0.196885866571)
        (quat.x, quat.y, quat.z, quat.w) = (0.0, 0.0, 0.0, 1.0)
        timeout = 20.0
        self.setOrientGoal(pos, quat, timeout)

        #moving to high in front of chest, pointing down:
        (pos.x, pos.y, pos.z) = (0.677839595079, -0.1569018662, 0.1919789999723)
        (quat.x, quat.y, quat.z, quat.w) = (0.13867505,  0.13867505,  0.13867505,  0.97072534)
        timeout = 20.0
        self.setOrientGoal(pos, quat, timeout)
        
        return True

    
if __name__ == '__main__':

    import optparse
    p = optparse.OptionParser()
    opt, args = p.parse_args()

    # Initial variables
    d_robot    = 'pr2'
    controller = 'static'
    arm        = 'r'

    rospy.init_node('arm_reacher')    
    ara = armReachAction(d_robot, controller, arm)
    rospy.spin()

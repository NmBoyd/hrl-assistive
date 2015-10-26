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
#

#  \author Daehyung Park (Healthcare Robotics Lab, Georgia Tech.)

# system library
import time, sys
import datetime

# ROS library
import rospy, roslib
roslib.load_manifest('hrl_manipulation_task')

# HRL library
from hrl_srvs.srv import String_String
import hrl_lib.util as ut

if __name__ == '__main__':

    rospy.init_node('feed_client')

    rospy.wait_for_service("/arm_reach_enable")
    armReachActionLeft  = rospy.ServiceProxy("/arm_reach_enable", String_String)
    armReachActionRight = rospy.ServiceProxy("/right/arm_reach_enable", String_String)

    print armReachActionRight("initScooping")
    print armReachActionLeft("initScooping")
    print armReachActionLeft("getBowlPos")
    print armReachActionLeft('lookAtBowl')
    print armReachActionLeft("test")
    sys.exit()
    
    
    ## Scooping -----------------------------------    
    print "Initializing left arm for scooping"
    print armReachActionLeft("initScooping")
    print armReachActionRight("initScooping")
    
    #ut.get_keystroke('Hit a key to proceed next')        
    print armReachActionLeft("getBowlPos")
    print armReachActionLeft('lookAtBowl')

    print "Running scooping!"
    print armReachActionLeft("runScooping")

    ## Feeding -----------------------------------
    print "Initializing left arm for feeding"
    print armReachActionRight("initFeeding")
    print armReachActionLeft("initFeeding")

    print "Detect ar tag on the head"
    print armReachActionLeft('lookAtMouth')
    print armReachActionLeft("getHeadPos")
    ut.get_keystroke('Hit a key to proceed next')        

    print "Running feeding!"
    print armReachActionLeft("runFeeding1")
    print armReachActionLeft("runFeeding2")

    
    ## t1 = datetime.datetime.now()
    ## t2 = datetime.datetime.now()
    ## t  = t2-t1
    ## print "time delay: ", t.seconds
    

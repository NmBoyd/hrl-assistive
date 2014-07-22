#!/usr/bin/env python


import numpy as np
import math as m
import openravepy as op
import copy
import os.path

import time
import roslib
roslib.load_manifest('hrl_base_selection')
roslib.load_manifest('hrl_haptic_mpc')
import rospy, rospkg
import tf
from geometry_msgs.msg import PoseStamped
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
from matplotlib.ticker import LinearLocator, FormatStrFormatter
import matplotlib.pyplot as plt
from matplotlib.path import Path
import matplotlib.patches as patches

from sensor_msgs.msg import JointState
from std_msgs.msg import String
import hrl_lib.transforms as tr
from hrl_base_selection.srv import BaseMove, BaseMove_multi
from visualization_msgs.msg import Marker
from helper_functions import createBMatrix, Bmat_to_pos_quat
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from matplotlib.cbook import flatten

import pickle as pkl
roslib.load_manifest('hrl_lib')
from hrl_lib.util import save_pickle, load_pickle
import tf.transformations as tft
from score_generator import ScoreGenerator
import data_clustering as clust

import hrl_lib.util as ut

class DataReader(object):
    
    def __init__(self,subject='sub6_shaver',data_start=0,data_finish=5,model='chair',task='shaving',pos_clust=5,ori_clust=1):
        self.score_sheet = []
        self.tf_listener = tf.TransformListener()

        self.subject = subject
        self.data_start = data_start
        self.data_finish = data_finish

        self.model = model
        self.max_distance = 0.05#5#0.2
        self.task = task
        self.num_goal_locations = 1
        self.pos_clust=pos_clust
        self.ori_clust=ori_clust  

    def get_raw_data(self):
        rospack = rospkg.RosPack()
        pkg_path = rospack.get_path('hrl_base_selection')
        #tool_init_pos = np.array([0.357766509056, 0.593838989735, 0.936517715454])
        #tool_init_rot = np.array([-0.23529052448, -0.502738550591, 3.00133908425])
        #head_init_pos = np.array([-0.142103180289, 0.457304298878, 1.13128328323]) 
        #head_init_rot = np.array([0.304673484999, -0.304466132626, 0.579344748594])
        #world_B_headinit = createBMatrix(head_init_pos,tft.quaternion_from_euler(head_init_rot[0],head_init_rot[1],head_init_rot[2],'rxyz'))
        #world_B_toolinit = createBMatrix(tool_init_pos,tft.quaternion_from_euler(tool_init_rot[0],tool_init_rot[1],tool_init_rot[2],'rxyz'))
        self.file_length = 0
        
        world_B_headc_raw_data = np.array([map(float,line.strip().split()) for line in open(''.join([pkg_path,'/data/',self.subject,'_head.log']))])
        world_B_tool_raw_data = np.array([map(float,line.strip().split()) for line in open(''.join([pkg_path,'/data/',self.subject,'_tool.log']))]) 

        #dist = []
        #for num,line in enumerate(world_B_headc_raw_data):
            #dist.append(np.linalg.norm(world_B_headc_raw_data[num,1:4] - world_B_tool_raw_data[num,1:4]))
        #print 'raw distance: \n',np.min(np.array(dist))
        
        # max_length is the length of the shorter of the two files. They sometimes differ in length by a few points.
        max_length = np.min([len(world_B_headc_raw_data),len(world_B_tool_raw_data)])

        # If data_finish is 'end' then it does from whatever is the start data to the end. self.length is the number of data points we are looking at.
        if self.data_finish == 'end':
            self.data_finish = max_length



        self.length = np.min(np.array([max_length,self.data_finish-self.data_start]))
        

        world_B_headc_data = np.zeros([self.length,4,4])
        world_B_tool_data = np.zeros([self.length,4,4])

        for num,line in enumerate(world_B_headc_raw_data[self.data_start:self.data_finish]):
            world_B_headc_data[num] = np.array(createBMatrix([line[1],line[2],line[3]],tft.quaternion_from_euler(line[4],line[5],line[6],'rxyz')))

        for num,line in enumerate(world_B_tool_raw_data[self.data_start:self.data_finish]):
            world_B_tool_data[num] = np.array(createBMatrix([line[1],line[2],line[3]],tft.quaternion_from_euler(line[4],line[5],line[6],'rxyz')))

        # I don't think data was collected on the tool tip, so I don't know what this data is. It has way more data than the others'
        #raw_tool_tip_data = np.array([map(float,line.strip().split()) for line in open(''.join([pkg_path,'/data/sub1_shaver_self_1_tool_tip.log']))])
        #tool_tip_data = np.zeros([len(raw_tool_tip_data),4,4])

        #for num,line in enumerate(raw_tool_tip_data):
        #    tool_tip_data[num] = np.array(createBMatrix([line[2],line[3],line[4]],tft.quaternion_from_euler#(line[5],line[6],line[7],'rxyz')))
        self.distance = []
        self.raw_goal_data = [] #np.zeros([self.length,4,4])
        self.max_start_distance = 0.2
        i = 0
        while self.raw_goal_data == []:
            temp = np.array(np.matrix(world_B_headc_data[i]).I*np.matrix(world_B_tool_data[i]))
            if np.linalg.norm(temp[0:3,3])<self.max_start_distance:
                self.raw_goal_data.append(temp)
            else:
                i+=1


        for num in xrange(1,self.length):
            temp = np.array(np.matrix(world_B_headc_data[num]).I*np.matrix(world_B_tool_data[num]))
            pos2,ori2=Bmat_to_pos_quat(temp)
            pos1,ori1=Bmat_to_pos_quat(self.raw_goal_data[len(self.raw_goal_data)-1])
           
            if np.linalg.norm(pos1-pos2)<self.max_distance:
                self.raw_goal_data.append(temp)
                self.file_length+=1
                self.distance.append(np.linalg.norm(temp[0:3,3]))
                #print 'This point has a distance of: ',np.linalg.norm(temp[0:3,3])
                #self.distance.append(np.linalg.norm(temp[0:3,3]))
            #goal_values[num,0:3] = [round(self.raw_goal_data[num,0,3],2),round(self.raw_goal_data[num,1,3],2),round(self.raw_goal_data[num,2,3],2)]
            #(rotx,roty,rotz) = tft.euler_from_matrix(self.raw_goal_data[num],'rxyz')
            #goal_values[num,3:6] = np.array([round(rotx,1),round(roty,1),round(rotz,1)])
            #temp = copy.copy(tft.euler_matrix(goal_values[num,3],goal_values[num,4],goal_values[num,5],'rxyz'))
            #temp[0,3] = goal_values[num,0]
            #temp[1,3] = goal_values[num,1]
            #temp[2,3] = goal_values[num,2]
            #if np.linalg.norm(temp[0:3,3])<self.max_distance:
            #    self.clustered_goal_data.append(temp)
            #self.clustered_goal_data[num] = copy.copy(tft.euler_matrix(goal_values[num,3],goal_values[num,4],goal_values[num,5],'rxyz'))
            #self.clustered_goal_data[num,0,3] = goal_values[num,0]
            #self.clustered_goal_data[num,1,3] = goal_values[num,1]
            #self.clustered_goal_data[num,2,3] = goal_values[num,2]
# + np.matrix(tft.translation_matrix(goal_values[num,0:3]))))
            #    self.distance.append(np.linalg.norm(temp[0:3,3]))
        self.raw_goal_data = np.array(self.raw_goal_data)
        return self.raw_goal_data

    def cluster_data(self):
        if len(self.raw_goal_data)<self.pos_clust:
            self.pos_clust = len(self.raw_goal_data)
        if len(self.raw_goal_data)<self.ori_clust:
            self.ori_clust = len(self.raw_goal_data)

        
        enough = False
        iter = 0
        while not enough and (iter<10):
            iter +=1
            cluster = clust.DataCluster(self.pos_clust,0.01,self.ori_clust,0.02)
            self.clustered_goal_data,number,num_pos_clusters, = cluster.clustering(self.raw_goal_data)
            if num_pos_clusters == self.pos_clust:
                self.pos_clust +=10
            else:
                enough = True
        #print 'Raw data: \n',self.raw_goal_data[0:20]
        #print 'Clustered data: \n',self.clustered_goal_data[0:20]



        #print 'Now finding how many unique goals there are. Please wait; this can take up to a couple of minutes.'
        #seen_items = []
        #self.goal_unique = [] 
        #for item in self.clustered_goal_data:
        #    if not (any((np.array_equal(item, x)) for x in seen_items)):
        #        if np.linalg.norm(item[0:3,3])<0.2:
        #            self.goal_unique.append([item,1.0/len(self.clustered_goal_data)])
        #            seen_items.append(item)
        #    else:
        #        #print 'item is: ', item
        #        #print 'score unique is: ',self.goal_unique
        #        for num,i in enumerate(self.goal_unique):
        #            if np.array_equal(item,i[0]):
        #                #print 'got here'
        #                self.goal_unique[num][1]=1.0/len(self.clustered_goal_data)+self.goal_unique[num][1]
        #self.goal_unique = np.array(self.goal_unique)
        #print 'final score unique is: ',self.goal_unique
        self.goal_unique = [] 
        for num in xrange(len(number)):
            self.goal_unique.append([self.clustered_goal_data[num],(float(number[num][0]))/(float(np.array(number).sum()))])
            #print 'I am appending this to distance: ', np.linalg.norm(self.clustered_goal_data[num][0:3,3])
            #if (num > 200) and (num < 240):
            #print 'clustered goal data number: ',num,'\n',self.clustered_goal_data[num]
            #print 'Comes up XX number times: ',number[num][0]
            #print 'has a distance of: ',np.linalg.norm(self.clustered_goal_data[num][0:3,3])
        #print 'distance: ',np.array(self.distance)
        self.goal_unique = np.array(self.goal_unique)
        #print 'Goal unique is \n',self.goal_unique
        self.pos_data = []
        self.cluster_distance = []
        for item in self.clustered_goal_data:
            self.pos_data.append([item[0,3],item[1,3],item[2,3]])
            self.cluster_distance.append(np.linalg.norm(item[0:3,3]))
        self.pos_data = np.array(self.pos_data)
        print 'Total number of goals as summed from the clustering: ',np.array(number).sum()
        print 'There are were %i total goals, %i goals within sensible distance, and %i unique goals within sensible distance of head center (0.2m)'%(self.length,len(self.raw_goal_data),len(self.goal_unique))
        
        print 'Minimum distance between center of head and goal location from raw data = ',np.min(np.array(self.distance))
        print 'Minimum distance between center of head and goal location from clustered data = ',np.min(np.array(self.cluster_distance))
        return self.clustered_goal_data,self.goal_unique



#        fig = plt.figure()
#        ax = fig.add_subplot(111, projection='3d')
#        Xhead  = world_B_head_data[:,0,3]
#        Yhead  = world_B_head_data[:,1,3]
#        Zhead = world_B_head_data[:,2,3]
#        Xtool  = world_B_tool_data[:,0,3]
#        Ytool  = world_B_tool_data[:,1,3]
#        Ztool = world_B_tool_data[:,2,3]
#        #print X,len(X),Y,len(Y),Z,len(Z)
#        #c  = 'b'
#        ax.scatter(Xhead, Yhead, Zhead,s=40, c='b',alpha=.5)
#        ax.scatter(Xtool, Ytool, Ztool,s=40, c='r',alpha=.5)
#        #surf = ax.scatter(X, Y, Z,s=40, c=c,alpha=.5)
#        #surf = ax.scatter(X, Y,s=40, c=c,alpha=.6)
#        ax.set_xlabel('X Axis')
#        ax.set_ylabel('Y Axis')
#        ax.set_zlabel('Z Axis')

        #fig.colorbar(surf, shrink=0.5, aspect=5)
#        plt.show()

    def generate_score(self,allow_multiple=False,viz_rviz=True):
        self.num_base_locations = 1
        mytargets = 'all_goals'
        mytask = self.task #'shaving'
        #start = 0
        #end = 3
        myGoals = copy.copy(self.goal_unique)#[self.data_start:self.data_finish]
        print 'There are ',len(myGoals),' goals being sent to score generator.'
        #print myGoals
        selector = ScoreGenerator(visualize=False,targets=mytargets,goals = myGoals,model=self.model,tf_listener=self.tf_listener)
        if viz_rviz:
            selector.show_rviz()
        #print 'Goals: \n',self.clustered_goal_data[0:4]
        #print tft.quaternion_from_matrix(self.clustered_goal_data[0])
        self.score_sheet = selector.handle_score()
        old_max_score = np.max(self.score_sheet[:,4])
        print 'The max reach score (% out of 1.00) I got when using only 1 base position was: ', np.max(self.score_sheet[:,4])
        ## Handles the option of getting multiple goal positions
        if allow_multiple:
            for num_base_locations in xrange(2,5):
                if (old_max_score<.95) and (num_base_locations <= len(myGoals)):
                    print 'Less than 95% of goal positions reachable from ',num_base_locations-1, ' base position(s). I should check if I can reach more goals using another base position.'
                    print 'Once again, it is 60-100 seconds calculation time per goal location.'
                    scores=[]
                    new_score = []
                    new_max_score = 0
                    goalCluster = []
                    cluster = clust.DataCluster(num_base_locations,0.001,1,0.02)
                    clust_numbers = cluster.pos_clustering(self.pos_data)
                    print 'Clusters assigned to groups: \n',clust_numbers
                    for i in xrange(num_base_locations):
                        goalCluster = []
                        for num,item in enumerate(self.goal_unique):
                            if clust_numbers[num] == i:
                                goalCluster.append(item)
                        goalCluster = np.array(goalCluster)
                        print 'The goals being evaluated at this base position are: \n',goalCluster
                        selector = ScoreGenerator(visualize=False,targets=mytargets,goals = goalCluster,model=self.model,tf_listener=self.tf_listener)
                        this_score = selector.handle_score()
                        new_max_score += np.max(this_score[:,4])
                        #print 'New max score being calculated: ',new_max_score
                        scores.append(this_score)
                    #old_max_score = 0
                    #for i in xrange(self.num_base_locations):
                    #    old_max_score += np.max(self.score_sheet[:,4+2*i])
                    print 'Old max score for ',self.num_base_locations,' base locations is: ',old_max_score
                    print 'New max reach score for ',num_base_locations,' base locations is: ',new_max_score
                    if new_max_score > old_max_score:
                        old_max_score = copy.copy(new_max_score)
                        for i in xrange(len(scores[0])):
                            score_line = []
                            score_line.append(list(scores[0][i,0:6]))
                            for j in xrange(1,num_base_locations):
                                score_line.append(list(scores[j][i,4:6]))
                            score_line = list(flatten(score_line))
                            new_score.append(score_line)
                        self.score_sheet = copy.copy(np.array(new_score))
                        self.num_base_locations = num_base_locations
        #print 'number of scores',len(scores)

        #print 'sample item from score sheet is: ',self.score_sheet[0]
        rospack = rospkg.RosPack()
        pkg_path = rospack.get_path('hrl_base_selection')
        save_pickle(self.score_sheet,''.join([pkg_path, '/data/',self.model,'_',self.task,'_',mytargets,'_numbers_',str(self.data_start),'_',str(self.data_finish),'_',self.subject,'.pkl']))

        if os.path.isfile(''.join([pkg_path, '/data/',self.task,'_score_data.pkl'])):
            data1 = load_pickle(''.join([pkg_path, '/data/',self.task,'_score_data.pkl']))
            if  (np.array_equal(data1[:,0:2],self.score_sheet[:,0:2])):
                data1[:,3] = self.score_sheet[:,3]*.25+data1[:,3]*.75
            else:
                print 'Something is messed up with the score sheets. The saved score sheet does not match up with the new score sheet.'
            #for num,i in enumerate(data1):
                #data1[num,3]=self.score_sheet[num,3]+i[3]
            save_pickle(data1,''.join([pkg_path, '/data/',self.task,'_score_data.pkl']))
            print 'There was existing score data for this task. I added the new data to the previous data.'
        else:
            save_pickle(self.score_sheet,''.join([pkg_path, '/data/',self.task,'_score_data.pkl']))
            print 'There was no existing score data for this task. I therefore created a new file.'

    def generate_library(self):
        mytargets = 'all_goals'
        mytask = self.task # 'shaving'
        #start = 0
        #end = 3
        myGoals = copy.copy(self.goal_unique)#[self.data_start:self.data_finish]
        print 'There are ',len(myGoals),' goals being sent to score generator.'
        #print myGoals
        selector = ScoreGenerator(visualize=False,targets=mytargets,goals = myGoals,model=self.model,tf_listener=self.tf_listener)
        #print 'Goals: \n',self.clustered_goal_data[0:4]
        #print tft.quaternion_from_matrix(self.clustered_goal_data[0])
        self.score_sheet = selector.handle_score()
    
        rospack = rospkg.RosPack()
        pkg_path = rospack.get_path('hrl_base_selection')
        save_pickle(self.score_sheet,''.join([pkg_path, '/data/',self.model,'_',self.task,'_',mytargets,'_numbers_',str(self.data_start),'_',str(self.data_finish),'_',self.subject,'.pkl']))

        if os.path.isfile(''.join([pkg_path, '/data/',self.task,'_score_data.pkl'])):
            data1 = load_pickle(''.join([pkg_path, '/data/',self.task,'_score_data.pkl']))
            if  (np.array_equal(data1[:,0:2],self.score_sheet[:,0:2])):
                data1[:,3] += self.score_sheet[:,3]/3
            else:
                print 'Something is messed up with the score sheets. The saved score sheet does not match up with the new score sheet.'
            #for num,i in enumerate(data1):
                #data1[num,3]=self.score_sheet[num,3]+i[3]
            save_pickle(data1,''.join([pkg_path, '/data/',self.task,'_score_data.pkl']))
            print 'There was existing score data for this task. I added the new data to the previous data.'
        else:
            save_pickle(self.score_sheet,''.join([pkg_path, '/data/',self.task,'_score_data.pkl']))
            print 'There was no existing score data for this task. I therefore created a new file.'


    
        #for num,line in enumerate(raw_goal_data):
        #    goal_values[num] = np.array([m.acos(line[0,0]),line[0,3],line[1,3],line[2,3]])

    def plot_score(self,load=False):
        # Plot the score as a scatterplot heat map
        #print 'score_sheet:',score_sheet
        rospack = rospkg.RosPack()
        pkg_path = rospack.get_path('hrl_base_selection')
        if load:
            print 'I am tring to load data to plot.'
            if os.path.isfile(''.join([pkg_path, '/data/',self.task,'_score_data.pkl'])):
                data=load_pickle(''.join([pkg_path, '/data/',self.task,'_score_data.pkl']))
                print 'Successful load. Will plot the latest and greatest version of the score sheet.'
            else:
                print 'I am only plotting the data that I just processed. I could not find what to load.'
                data=self.score_sheet
        else:
            print 'I am only plotting the data that I just processed. I did not load anything to plot.'
            data=self.score_sheet
        score2d_temp = []
        #print t
        for i in np.arange(-1.5,1.55,.05):
            for j in np.arange(-1.5,1.55,.05):
                temp = []
                for item in data:
                    newline = []
                #print 'i is:',i
                #print 'j is:',j
                    if item[0]==i and item[1]==j:
                        newline.append([i,j,item[3]])
                        for k in xrange(self.num_base_locations):
                            newline.append(item[int(4 + 2*k)])
                            newline.append(item[int(5 + 2*k)])
                        #print 'newest line ',list(flatten(newline))
                        temp.append(list(flatten(newline)))
                temp=np.array(temp)
                temp_max = []
                temp_max.append(np.max(temp[:,2]))
                for k in xrange(self.num_base_locations):
                    temp_max.append(np.max(temp[:,int(3+2*k)]))
                    temp_max.append(np.max(temp[:,int(4+2*k)]))
                #print 'temp_max is ',temp_max
                score2d_temp.append(list(flatten([i,j,temp_max])))

        #print '2d score:',np.array(score2d_temp)[0]

        seen_items = []
        score2d = [] 
        for item in score2d_temp:
            #any((a == x).all() for x in my_list)
            #print 'seen_items is: ',seen_items
            #print 'item is: ',item
            #print (any((item == x) for x in seen_items))
            if not (any((item == x) for x in seen_items)):
            #if item not in seen_items:
                #print 'Just added the item to score2d'
                score2d.append(item)
                seen_items.append(item)
        score2d = np.array(score2d)
        #print 'score2d with no repetitions',score2d
        #for item in score2d:
        #    if (item[0]<0.5) and (item[0]>-0.5) and (item[1]<0.5) and (item[1]>-0.5):
        #        print item


        if self.model == 'chair':
            verts_subject = [(-.438, -.32885), # left, bottom
                             (-.438, .32885), # left, top
                             (.6397, .32885), # right, top
                             (.6397, -.32885), # right, bottom
                             (0., 0.), # ignored
                        ]
        elif self.model == 'bed':
            verts_subject = [(-.2954, -.475), # left, bottom
                             (-.2954, .475), # left, top
                             (1.805, .475), # right, top
                             (1.805, -.475), # right, bottom
                             (0., 0.), # ignored
                            ]
        
        
        verts_pr2 = [(-1.5,  -1.5), # left, bottom
                     ( -1.5, -.835), # left, top
                     (-.835, -.835), # right, top
                     (-.835,  -1.5), # right, bottom
                     (   0.,    0.), # ignored
                    ]
    
        codes = [Path.MOVETO,
                 Path.LINETO,
                 Path.LINETO,
                 Path.LINETO,
                 Path.CLOSEPOLY,
                ]
           
        path_subject = Path(verts_subject, codes)
        path_pr2 = Path(verts_pr2, codes)
    
        patch_subject = patches.PathPatch(path_subject, facecolor='orange', lw=2)        
        patch_pr2 = patches.PathPatch(path_pr2, facecolor='orange', lw=2)
        
        X  = score2d[:,0]
        Y  = score2d[:,1]
        #Th = score_sheet[:,2]
        c3  = score2d[:,2]

        fig3 = plt.figure(1)
        ax3 = fig3.add_subplot(111)
        surf3 = ax3.scatter(X, Y,s=60, c=c3,alpha=1)
        ax3.set_xlabel('X Axis')
        ax3.set_ylabel('Y Axis')
        fig3.colorbar(surf3, shrink=0.65, aspect=5)
        ax3.add_patch(patch_subject)
        ax3.add_patch(patch_pr2)
        ax3.set_xlim(-2,2)
        ax3.set_ylim(-2,2)
        fig3.set_size_inches(14,11,forward=True)
        if load:
            ax3.set_title(''.join(['Plot of personal space score from ',self.task]))
            plt.savefig(''.join([pkg_path, '/images/space_score_of_',self.task,'.png']), bbox_inches='tight')     
        else:
            ax3.set_title(''.join(['Plot of personal space score from ',self.subject,' on a ',self.model,' model.',' Data: (',str(self.data_start),' - ',str(self.data_finish),')']))
            plt.savefig(''.join([pkg_path, '/images/space_score_of_',self.model,'_',self.subject,'_numbers_',str(self.data_start),'_',str(self.data_finish),'.png']), bbox_inches='tight')


        print 'Number of base locations is: ',self.num_base_locations
        #print 'score2d ',score2d[0,:]
        for i in xrange(self.num_base_locations):
            
            c = copy.copy(score2d[:,3+2*i])
            c2 = copy.copy(score2d[:,4+2*i])

            fig = plt.figure(2+2*i)
            ax = fig.add_subplot(111)
            surf = ax.scatter(X, Y, s=60,c=c,alpha=1)
            ax.set_xlabel('X Axis')
            ax.set_ylabel('Y Axis')
            fig.colorbar(surf, shrink=0.65, aspect=5)
            ax.add_patch(patch_subject)
            ax.add_patch(patch_pr2)
            ax.set_xlim(-2,2)
            ax.set_ylim(-2,2)
            fig.set_size_inches(14,11,forward=True)
            if load:
                ax.set_title(''.join(['Plot of reach score from BP',str(i+1),' ',self.task]))
                plt.savefig(''.join([pkg_path, '/images/reach_score_of_BP',str(i+1),'_',self.task,'.png']), bbox_inches='tight')       
            else:
                ax.set_title(''.join(['Plot of reach score from BP',str(i+1),' ',self.subject,' on a ',self.model,' model.',' Data: (',str(self.data_start),' - ',str(self.data_finish),')']))
                plt.savefig(''.join([pkg_path, '/images/reach_score_of_BP',str(i+1),'_',self.model,'_',self.subject,'_numbers_',str(self.data_start),'_',str(self.data_finish),'.png']), bbox_inches='tight')
            
            fig2 = plt.figure(3+2*i)
            ax2 = fig2.add_subplot(111)
            surf2 = ax2.scatter(X, Y,s=60, c=c2,alpha=1)
            ax2.set_xlabel('X Axis')
            ax2.set_ylabel('Y Axis')
            fig2.colorbar(surf2, shrink=0.65, aspect=5)
            ax2.add_patch(patch_subject)
            ax2.add_patch(patch_pr2)
            ax2.set_xlim(-2,2)
            ax2.set_ylim(-2,2)
            fig2.set_size_inches(14,11,forward=True)
            if load:
                ax2.set_title(''.join(['Plot of manipulability score from BP',str(i+1),' ',self.task]))
                plt.savefig(''.join([pkg_path, '/images/manip_score_of_BP',str(i+1),'_',self.task,'.png']), bbox_inches='tight')     
            else:
                ax2.set_title(''.join(['Plot of manip score from BP',str(i+1),' ',self.subject,' on a ',self.model,' model.',' Data: (',str(self.data_start),' - ',str(self.data_finish),')']))
                plt.savefig(''.join([pkg_path, '/images/manip_score_of_BP',str(i+1),'_',self.model,'_',self.subject,'_numbers_',str(self.data_start),'_',str(self.data_finish),'.png']), bbox_inches='tight')

        plt.ion()                                                                                                 
        plt.show()                                                                                                
        ut.get_keystroke('Hit a key to proceed next')

    def plot_goals(self):
        fig = plt.figure()
        #fig = plt.gcf()
        fig.set_size_inches(14,11,forward=True)
        ax = fig.add_subplot(111, projection='3d')
        X  = self.clustered_goal_data[:,0,3]
        Y  = self.clustered_goal_data[:,1,3]
        Z = self.clustered_goal_data[:,2,3]
        #print X,len(X),Y,len(Y),Z,len(Z)
        c  = 'b'
        surf = ax.scatter(X, Y, Z,s=40, c=c,alpha=.5)
        #surf = ax.scatter(X, Y,s=40, c=c,alpha=.6)
        ax.set_xlabel('X Axis')
        ax.set_ylabel('Y Axis')
        ax.set_zlabel('Z Axis')

        ax.set_title(''.join(['Plot of goals from ',self.subject,'. Data: (',str(self.data_start),' - ',str(self.data_finish),')']))

        #fig.colorbar(surf, shrink=0.5, aspect=5)
        rospack = rospkg.RosPack()
        pkg_path = rospack.get_path('hrl_base_selection')
        ax.set_xlim(-.2,.2)
        ax.set_ylim(-.2,.2)
        ax.set_zlim(-.2,.2)
        #plt.savefig(''.join([pkg_path, '/images/goals_plot_',self.model,'_',self.subject,'_numbers_',str(self.data_start),'_',str(self.data_finish),'.png']), bbox_inches='tight')
        
        plt.ion()                                                                                                 
        plt.show()                                                                                                
        ut.get_keystroke('Hit a key to proceed next')

    def pub_rviz(self):
        self.num_base_locations = 1
        mytargets = 'all_goals'
        mytask = self.task #'shaving'
        #start = 0
        #end = 3
        myGoals = copy.copy(self.goal_unique)#[self.data_start:self.data_finish]
        print 'There are ',len(myGoals),' goals being sent to score generator.'
        #print myGoals
        selector = ScoreGenerator(visualize=False,targets=mytargets,goals = myGoals,model=self.model,tf_listener=self.tf_listener)
        selector.show_rviz()


if __name__ == "__main__":
    data_start=0
    data_finish='end' #4000 #'end'
    model = 'chair'
    subject='test1_shaver'
    pos_clust = 100
    ori_clust = 5
    rospy.init_node(''.join(['data_reader_',subject,'_',str(data_start),'_',str(data_finish),'_',str(int(time.time()))]))
    start_time = time.time()
    print 'Starting to convert data!'
    runData = DataReader(subject=subject,data_start=data_start,data_finish=data_finish,model=model,pos_clust=pos_clust,ori_clust=ori_clust)
    runData.get_raw_data()
    runData.cluster_data()
    print 'Time to convert data into useful matrices: %fs'%(time.time()-start_time)
    print 'Now starting to generate the score. This will take a long time if there were many goal locations.'
    start_time = time.time()
    runData.pub_rviz()
    #runData.plot_goals()
    #runData.generate_score(allow_multiple=True)
    print 'Time to generate all scores: %fs'%(time.time()-start_time)
    #print 'Now trying to plot the data. This might take a while for lots of data; depends on amount of data in score sheet. ~60 seconds.'
    #start_time = time.time()
    #runData.plot_score(load=False)
    print 'Time to plot score: %fs'%(time.time()-start_time)
    rospy.spin()





























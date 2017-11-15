#!/usr/bin/env python
import sys
import os
import numpy as np
import cPickle as pkl
import random
import math

# ROS
#import roslib; roslib.load_manifest('hrl_pose_estimation')

# Graphics
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from mpl_toolkits.mplot3d import Axes3D

# Machine Learning
from scipy import ndimage
from scipy.ndimage.filters import gaussian_filter
from scipy import interpolate
from scipy.misc import imresize
from scipy.ndimage.interpolation import zoom
import scipy.stats as ss
## from skimage import data, color, exposure
from sklearn.decomposition import PCA
from sklearn.preprocessing import normalize




# HRL libraries
import hrl_lib.util as ut
import pickle
#roslib.load_manifest('hrl_lib')
from hrl_lib.util import load_pickle

# Pose Estimation Libraries
from create_dataset_lib import CreateDatasetLib

#PyTorch libraries
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import transforms
from torch.autograd import Variable



MAT_WIDTH = 0.762 #metres
MAT_HEIGHT = 1.854 #metres
MAT_HALF_WIDTH = MAT_WIDTH/2
NUMOFTAXELS_X = 84#73 #taxels
NUMOFTAXELS_Y = 47#30
NUMOFOUTPUTDIMS = 3
NUMOFOUTPUTNODES = 10
INTER_SENSOR_DISTANCE = 0.0286#metres
LOW_TAXEL_THRESH_X = 0
LOW_TAXEL_THRESH_Y = 0
HIGH_TAXEL_THRESH_X = (NUMOFTAXELS_X - 1)
HIGH_TAXEL_THRESH_Y = (NUMOFTAXELS_Y - 1)


class DataVisualizer():
    '''Gets the directory of pkl database and iteratively go through each file,
    cutting up the pressure maps and creating synthetic database'''
    def __init__(self, pkl_directory, pathkey, opt):
        self.opt = opt
        self.sitting = False
        self.subject = 4
        self.armsup = False
        self.alldata = False
        self.verbose = True
        self.old = False
        self.normalize = True
        # Set initial parameters
        self.dump_path = pkl_directory.rstrip('/')

        self.mat_size = (NUMOFTAXELS_X, NUMOFTAXELS_Y)


        if self.opt.arms_only == True:
            self.output_size = (NUMOFOUTPUTNODES-6, NUMOFOUTPUTDIMS)
        else:
            self.output_size = (NUMOFOUTPUTNODES, NUMOFOUTPUTDIMS)

        if pathkey == 'lab_hd':
            train_val_loss = load_pickle(self.dump_path + '/train_val_losses.p')
            train_val_loss_desk = load_pickle(self.dump_path + '/train_val_losses_hcdesktop.p')
            train_val_loss_all = load_pickle(self.dump_path + '/train_val_losses_all.p')
            train_val_loss_171106 = load_pickle(self.dump_path + '/train_val_losses_171106.p')
            for key in train_val_loss:
                print key
            print '###########################  done with laptop #################'
            for key in train_val_loss_desk:
                print key
            print '###########################  done with desktop ################'
            for key in train_val_loss_171106:
                print key
            print '###########################  done with 171106 ################'
            for key in train_val_loss_all:
                print key
            print '###########################  done with mixed sitting/laying ################'



        elif pathkey == 'hc_desktop':
            train_val_loss_all = load_pickle(self.dump_path + '/train_val_losses_all.p')
            for key in train_val_loss_all:
                print key
            print '###########################  done with desktop ################'

        #handles, labels = plt.get_legend_handles_labels()
        #plt.legend(handles, labels)
        #print train_val_loss



        if self.subject == 1:
            #plt.plot(train_val_loss['epoch_flip_1'], train_val_loss['train_flip_1'],'b')
            #plt.plot(train_val_loss['epoch_1'], train_val_loss['train_1'], 'g')
            #plt.plot(train_val_loss['epoch_1'], train_val_loss['val_1'], 'k')
            #plt.plot(train_val_loss['epoch_flip_1'], train_val_loss['val_flip_1'], 'r')
            #plt.plot(train_val_loss['epoch_flip_shift_1'], train_val_loss['train_flip_shift_1'], 'g')
            #plt.plot(train_val_loss['epoch_flip_shift_1'], train_val_loss['val_flip_shift_1'], 'g')
            #plt.plot(train_val_loss['epoch_flip_shift_nd_1'], train_val_loss['val_flip_shift_nd_1'], 'g')
            #plt.plot(train_val_loss['epoch_flip_shift_nd_nohome_1'], train_val_loss['val_flip_shift_nd_nohome_1'], 'y')
            #plt.plot(train_val_loss['epoch_armsup_flip_shift_scale5_nd_nohome_1'], train_val_loss['train_armsup_flip_shift_scale5_nd_nohome_1'], 'b')
            #plt.plot(train_val_loss['epoch_armsup_flip_shift_scale5_nd_nohome_1'], train_val_loss['val_armsup_flip_shift_scale5_nd_nohome_1'], 'r')

            plt.plot(train_val_loss_desk['epoch_armsup_700e_1'], train_val_loss_desk['val_armsup_700e_1'], 'k',label='Raw Pressure Map Input')
            #plt.plot(train_val_loss['epoch_sitting_flip_700e_4'], train_val_loss['val_sitting_flip_700e_4'], 'c',label='Synthetic Flipping: $Pr(X=flip)=0.5$')
            #plt.plot(train_val_loss_desk['epoch_armsup_flip_shift_scale10_700e_1'],train_val_loss_desk['val_armsup_flip_shift_scale10_700e_1'], 'g',label='Synthetic Flipping+Shifting: $X,Y \sim N(\mu,\sigma), \mu = 0 cm, \sigma \~= 9 cm$')
            plt.plot(train_val_loss_desk['epoch_armsup_flip_shift_scale5_nd_nohome_700e_1'],train_val_loss_desk['val_armsup_flip_shift_scale5_nd_nohome_700e_1'], 'y', label='Synthetic Flipping+Shifting+Scaling: $S_C \sim N(\mu,\sigma), \mu = 1, \sigma \~= 1.02$')
            plt.legend()
            plt.ylabel('Mean squared error loss over 30 joint vectors')
            plt.xlabel('Epochs, where 700 epochs ~ 4 hours')
            plt.title('Subject 1 laying validation Loss, training performed on subjects 2, 3, 4, 5, 6, 7, 8')


        elif self.subject == 4:
            #plt.plot(train_val_loss['epoch_flip_4'], train_val_loss['train_flip_4'], 'g')
            #plt.plot(train_val_loss['epoch_flip_4'], train_val_loss['val_flip_4'], 'y')
            #plt.plot(train_val_loss['epoch_4'], train_val_loss['train_4'], 'b')
            #plt.plot(train_val_loss['epoch_4'], train_val_loss['val_4'], 'r')
            #plt.plot(train_val_loss['epoch_flip_shift_nd_4'], train_val_loss['val_flip_shift_nd_4'], 'b')
            #plt.plot(train_val_loss['epoch_flip_shift_nd_nohome_4'], train_val_loss['val_flip_shift_nd_nohome_4'], 'y')

            if pathkey == 'lab_hd': #results presented to hrl dressing 171106

                if self.opt.arms_only == True:
                    #plt.plot(train_val_loss_all['epoch_2to8_all_armsonly_fss_100b_adam_300e_4'],train_val_loss_all['train_2to8_all_armsonly_fss_100b_adam_300e_4'],'k', label='Synthetic Flipping+Shifting+Scaling')
                    plt.plot(train_val_loss_all['epoch_2to8_all_armsonly_fss_100b_adam_300e_4'],train_val_loss_all['val_2to8_all_armsonly_fss_100b_adam_300e_4'], 'c',label='Synthetic Flipping+Shifting+Scaling')
                    plt.plot(train_val_loss_all['epoch_2to8_all_armsonly_fss_115b_adam_100e_4'],train_val_loss_all['val_2to8_all_armsonly_fss_115b_adam_100e_4'], 'g',label='Synthetic Flipping+Shifting+Scaling')
                    plt.plot(train_val_loss_all['epoch_2to8_all_armsonly_fss_130b_adam_120e_4'],train_val_loss_all['val_2to8_all_armsonly_fss_130b_adam_120e_4'], 'y',label='Synthetic Flipping+Shifting+Scaling')
                    plt.plot(train_val_loss_all['epoch_2to8_all_armsonly_fss_115b_adam_350e_4'],train_val_loss_all['val_2to8_all_armsonly_fss_115b_adam_350e_4'], 'r',label='Synthetic Flipping+Shifting+Scaling')
                    plt.plot(train_val_loss_all['epoch_2to8_all_armsonly_fss_115b_adam_120e_lg1_4'],train_val_loss_all['val_2to8_all_armsonly_fss_115b_adam_120e_lg1_4'], 'b',label='Synthetic Flipping+Shifting+Scaling')
                    plt.plot(train_val_loss_all['epoch_2to8_all_armsonly_fss_115b_adam_200e_sm1_4'],
                             train_val_loss_all['val_2to8_all_armsonly_fss_115b_adam_200e_sm1_4'], 'm',
                             label='Synthetic Flipping+Shifting+Scaling')







                else:
                    plt.plot(train_val_loss['epoch_sitting_700e_4'],train_val_loss['val_sitting_700e_4'],'k', label='Raw Pressure Map Input')
                    plt.plot(train_val_loss['epoch_sitting_flip_700e_4'], train_val_loss['val_sitting_flip_700e_4'], 'c', label='Synthetic Flipping: $Pr(X=flip)=0.5$')
                    plt.plot(train_val_loss['epoch_sitting_flip_shift_nd_700e4'],train_val_loss['val_sitting_flip_shift_nd_700e4'], 'g', label='Synthetic Flipping+Shifting: $X,Y \sim N(\mu,\sigma), \mu = 0 cm, \sigma \~= 9 cm$')
                    plt.plot(train_val_loss['epoch_sitting_flip_shift_scale10_700e_4'],train_val_loss['val_sitting_flip_shift_scale10_700e_4'], 'y', label='Synthetic Flipping+Shifting+Scaling: $S_C \sim N(\mu,\sigma), \mu = 1, \sigma \~= 1.02$')
                    plt.plot(train_val_loss['epoch_alldata_flip_shift_scale5_nd_nohome_500e_4'],train_val_loss['val_alldata_flip_shift_scale5_nd_nohome_500e_4'], 'r',label='Standing+Sitting: Synthetic Flipping+Shifting+Scaling: $S_C \sim N(\mu,\sigma), \mu = 1, \sigma \~= 1.02$')
                #plt.plot(train_val_loss['epoch_sitting_flip_shift_scale5_700e_4'],train_val_loss['val_sitting_flip_shift_scale_700e_4'], 'y',label='Synthetic Flipping+Shifting+Scaling: $S_C \sim N(\mu,\sigma), \mu = 1, \sigma \~= 1.02$')

                    plt.plot(train_val_loss_171106['epoch_sitting_flip_shift_scale5_b50_700e_4'],train_val_loss_171106['train_sitting_flip_shift_scale5_b50_700e_4'], 'b', label='Synthetic Flipping+Shifting+Scaling: $S_C \sim N(\mu,\sigma), \mu = 1, \sigma \~= 1.02$')
                    plt.legend()
                    plt.ylabel('Mean squared error loss over 30 joint vectors')
                    plt.xlabel('Epochs, where 700 epochs ~ 4 hours')
                    plt.title('Subject 4 sitting validation Loss, training performed on subjects 2, 3, 5, 6, 7, 8')




        elif self.subject == 10:
            if pathkey == 'hc_desktop':
                plt.plot(train_val_loss_all['epoch_alldata_flip_shift_scale5_700e_10'],train_val_loss_all['train_alldata_flip_shift_scale5_700e_10'], 'g',label='Synthetic Flipping+Shifting+Scaling: $S_C \sim N(\mu,\sigma), \mu = 1, \sigma \~= 1.02$')
                plt.plot(train_val_loss_all['epoch_alldata_flip_shift_scale5_700e_10'],train_val_loss_all['val_alldata_flip_shift_scale5_700e_10'], 'y',label='Synthetic Flipping+Shifting+Scaling: $S_C \sim N(\mu,\sigma), \mu = 1, \sigma \~= 1.02$')


            #plt.plot(train_val_loss['epoch_flip_2'], train_val_loss['train_flip_2'], 'y')
            #plt.plot(train_val_loss['epoch_flip_2'], train_val_loss['val_flip_2'], 'g')
            #plt.plot(train_val_loss['epoch_flip_shift_nd_2'], train_val_loss['val_flip_shift_nd_2'], 'y')

        plt.axis([0,300,0,30000])
        plt.show()






    def validate_model(self):

        if self.sitting == True:
            validation_set = load_pickle(self.dump_path + '/subject_'+str(self.subject)+'/p_files/trainval_sitting_120rh_lh_rl_ll.p')
        elif self.armsup == True:
            validation_set = load_pickle(self.dump_path + '/subject_' + str(self.subject) + '/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head.p')
        elif True:
            validation_set = load_pickle(self.dump_path + '/subject_' + str(4) + '/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p')
        elif self.opt.arms_only == True:
            validation_set = load_pickle(self.dump_path + '/subject_' + str(4) + '/p_files/trainval_200rh1_lh1_100rh23_lh23_sit120rh_lh.p')
        else:
            validation_set = load_pickle(self.dump_path + '/subject_'+str(self.subject)+'/p_files/trainval_200rh1_lh1_rl_ll.p')

        test_dat = validation_set


        self.test_x_flat = []  # Initialize the testing pressure mat list
        for entry in range(len(test_dat)):
            self.test_x_flat.append(test_dat[entry][0])
        #test_x = self.preprocessing_pressure_array_resize(self.test_x_flat)
        #test_x = np.array(test_x)


        self.old = False
        if self.old == True:
            test_x = self.pad_pressure_mats(test_x)
            self.test_x_tensor = torch.Tensor(test_x)
        else:
            self.test_a_flat = []  # Initialize the testing pressure mat angle list
            for entry in range(len(test_dat)):
                self.test_a_flat.append(test_dat[entry][2])
            test_xa = self.preprocessing_create_pressure_angle_stack(self.test_x_flat, self.test_a_flat)
            test_xa = np.array(test_xa)
            self.test_x_tensor = torch.Tensor(test_xa)

        self.test_y_flat = []  # Initialize the ground truth list
        for entry in range(len(test_dat)):
            if self.opt.arms_only == True:
                self.test_y_flat.append(test_dat[entry][1][6:18])
            else:
                self.test_y_flat.append(test_dat[entry][1])
        self.test_y_tensor = torch.Tensor(self.test_y_flat)
        self.test_y_tensor = torch.mul(self.test_y_tensor, 1000)


        #print len(validation_set)
        batch_size = 1

        if self.old == True:
            self.test_x_tensor = self.test_x_tensor.unsqueeze(1)
        self.test_dataset = torch.utils.data.TensorDataset(self.test_x_tensor, self.test_y_tensor)
        self.test_loader = torch.utils.data.DataLoader(self.test_dataset, batch_size, shuffle=True)


        if self.sitting == True:
            model = torch.load(self.dump_path + '/subject_'+str(self.subject)+'/p_files/convnet_sitting_1to8_flip_shift_scale5_700e.pt')
        elif self.armsup == True:
            model = torch.load(self.dump_path + '/subject_' + str(self.subject) + '/p_files/convnet_1to8_armsup_700e.pt')
        elif self.alldata == True:
            model = torch.load(self.dump_path + '/subject_' + str(self.subject) + '/p_files/convnet_all.pt')
        elif self.opt.arms_only == True:
            model = torch.load(self.dump_path + '/subject_' + str(self.subject) + '/p_files/convnet_2to8_all_armsonly_fss_115b_adam_350e_4.pt')
        else:
            model = torch.load(self.dump_path + '/subject_'+str(self.subject)+'/p_files/convnet_1to8_flip_shift_nodrop_nohome.pt')

        count = 0
        for batch_idx, batch in enumerate(self.test_loader):
            count += 1
            #print count

            images, targets = Variable(batch[0]), Variable(batch[1])

            #print targets.size()

            scores = model(images)

            #print scores.size()
            self.print_error(targets,scores)

            self.im_sample = batch[0].numpy()
            self.im_sample = np.squeeze(self.im_sample[0, :])
            self.tar_sample = batch[1].numpy()
            self.tar_sample = np.squeeze(self.tar_sample[0, :]) / 1000
            self.sc_sample = scores.data.numpy()
            self.sc_sample = np.squeeze(self.sc_sample[0, :]) / 1000
            self.sc_sample = np.reshape(self.sc_sample, self.output_size)

            self.visualize_pressure_map(self.im_sample, self.tar_sample, self.sc_sample)





        return mean, stdev

    def pad_pressure_mats(self,NxHxWimages):
        padded = np.zeros((NxHxWimages.shape[0],NxHxWimages.shape[1]+20,NxHxWimages.shape[2]+20))
        padded[:,10:74,10:37] = NxHxWimages
        NxHxWimages = padded
        return NxHxWimages


    def preprocessing_pressure_array_resize(self, data):
        '''Will resize all elements of the dataset into the dimensions of the
        pressure map'''
        p_map_dataset = []
        for map_index in range(len(data)):
            #print map_index, self.mat_size, 'mapidx'
            #Resize mat to make into a matrix
            p_map = np.reshape(data[map_index], self.mat_size)
            #if self.normalize == True:
            #    p_map = normalize(p_map, norm='l2')

            p_map_dataset.append(p_map)
        if self.verbose: print len(data[0]),'x',1, 'size of an incoming pressure map'
        if self.verbose: print len(p_map_dataset[0]),'x',len(p_map_dataset[0][0]), 'size of a resized pressure map'
        return p_map_dataset

    def preprocessing_create_pressure_angle_stack(self,x_data,a_data):
        p_map_dataset = []
        for map_index in range(len(x_data)):
            # print map_index, self.mat_size, 'mapidx'
            # Resize mat to make into a matrix
            p_map = np.reshape(x_data[map_index], self.mat_size)
            a_map = np.zeros_like(p_map) + a_data[map_index]




            p_map_dataset.append([p_map, a_map])
        if self.verbose: print len(x_data[0]), 'x', 1, 'size of an incoming pressure map'
        if self.verbose: print len(p_map_dataset[0][0]), 'x', len(p_map_dataset[0][0][0]), 'size of a resized pressure map'
        if self.verbose: print len(p_map_dataset[0][1]), 'x', len(p_map_dataset[0][1][0]), 'size of the stacked angle mat'

        return p_map_dataset


    def print_error(self, target, score, data = None):
        error = (score - target)
        error = error.data.numpy()
        error_avg = np.mean(error, axis=0) / 10
        error_avg = np.reshape(error_avg, self.output_size)
        error_avg = np.reshape(np.array(["%.2f" % w for w in error_avg.reshape(error_avg.size)]),
                               self.output_size)
        if self.opt.arms_only == True:
            error_avg = np.transpose(np.concatenate(([['Average Error for Last Batch', '       ', 'R Elbow', 'L Elbow', 'R Hand ', 'L Hand ']], np.transpose(
                np.concatenate(([['', '', ''], [' x, cm ', ' y, cm ', ' z, cm ']], error_avg))))))
        else:
            error_avg = np.transpose(np.concatenate(([['Average Error for Last Batch', '       ', 'Head   ',
                                                       'Torso  ', 'R Elbow', 'L Elbow', 'R Hand ', 'L Hand ',
                                                       'R Knee ', 'L Knee ', 'R Foot ', 'L Foot ']], np.transpose(
                np.concatenate(([['', '', ''], [' x, cm ', ' y, cm ', ' z, cm ']], error_avg))))))
        print data, error_avg

        error_std = np.std(error, axis=0) / 10
        error_std = np.reshape(error_std, self.output_size)
        error_std = np.reshape(np.array(["%.2f" % w for w in error_std.reshape(error_std.size)]),
                               self.output_size)

        if self.opt.arms_only == True:
            error_std = np.transpose(np.concatenate(([['Error Standard Deviation for Last Batch', '       ','R Elbow', 'L Elbow', 'R Hand ', 'L Hand ']], np.transpose(
                np.concatenate(([['', '', ''], ['x, cm', 'y, cm', 'z, cm']], error_std))))))
        else:
            error_std = np.transpose(
                np.concatenate(([['Error Standard Deviation for Last Batch', '       ', 'Head   ', 'Torso  ',
                                  'R Elbow', 'L Elbow', 'R Hand ', 'L Hand ', 'R Knee ', 'L Knee ',
                                  'R Foot ', 'L Foot ']], np.transpose(
                    np.concatenate(([['', '', ''], ['x, cm', 'y, cm', 'z, cm']], error_std))))))
        print data, error_std

    def visualize_pressure_map(self, p_map, targets_raw=None, scores_raw = None, p_map_val = None, targets_val = None, scores_val = None):
        print p_map.shape, 'pressure mat size', targets_raw.shape, 'target shape'

        if self.old == False:
            p_map = p_map[0,:,:]
            if p_map_val is not None:
                p_map_val = p_map_val[0,:,:]



        plt.close()
        plt.pause(0.0001)

        fig = plt.figure()
        mngr = plt.get_current_fig_manager()
        # to put it into the upper left corner for example:
        mngr.window.setGeometry(50, 100, 840, 705)

        plt.pause(0.0001)

        # set options
        ax1 = fig.add_subplot(1, 1, 1)
        #ax2 = fig.add_subplot(1, 2, 2)


        xlim = [-2.0, 49.0]
        ylim = [86.0, -2.0]
        ax1.set_xlim(xlim)
        ax1.set_ylim(ylim)
        #

        # background
        ax1.set_axis_bgcolor('cyan')
        #

        # Visualize pressure maps
        ax1.imshow(p_map, interpolation='nearest', cmap=
        plt.cm.bwr, origin='upper', vmin=0, vmax=100)

        if p_map_val is not None:
            ax2.set_xlim(xlim)
            ax2.set_ylim(ylim)
            ax2.set_axis_bgcolor('cyan')
            ax2.imshow(p_map_val, interpolation='nearest', cmap=
            plt.cm.bwr, origin='upper', vmin=0, vmax=100)
            ax2.set_title('Validation Sample \n Targets and Estimates')

        # Visualize targets of training set
        if targets_raw is not None:

            if len(np.shape(targets_raw)) == 1:
                targets_raw = np.reshape(targets_raw, (len(targets_raw) / 3, 3))

            #targets_raw[:, 0] = ((targets_raw[:, 0] - 0.3718) * -1) + 0.3718
            #print targets_raw
            #extra_point = np.array([[0.,0.3718,0.7436],[0.,0.,0.]])
            #extra_point = extra_point/INTER_SENSOR_DISTANCE
            #ax1.plot(extra_point[0,:],extra_point[1,:], 'r*', ms=8)

            target_coord = targets_raw[:, :2] / INTER_SENSOR_DISTANCE
            target_coord[:, 1] -= (NUMOFTAXELS_X - 1)
            target_coord[:, 1] *= -1.0
            ax1.plot(target_coord[:, 0], target_coord[:, 1], marker = 'o', linestyle='None', markerfacecolor = 'green',markeredgecolor='black', ms=8)

        plt.pause(0.0001)

        #Visualize estimated from training set
        if scores_raw is not None:
            if len(np.shape(scores_raw)) == 1:
                scores_raw = np.reshape(scores_raw, (len(scores_raw) / 3, 3))
            target_coord = scores_raw[:, :2] / INTER_SENSOR_DISTANCE
            target_coord[:, 1] -= (NUMOFTAXELS_X - 1)
            target_coord[:, 1] *= -1.0
            ax1.plot(target_coord[:, 0], target_coord[:, 1], marker = 'o', linestyle='None', markerfacecolor = 'white',markeredgecolor='black', ms=8)
        ax1.set_title('Training Sample \n Targets and Estimates')
        plt.pause(0.0001)

        # Visualize targets of validation set
        if targets_val is not None:
            if len(np.shape(targets_val)) == 1:
                targets_val = np.reshape(targets_val, (len(targets_val) / 3, 3))
            target_coord = targets_val[:, :2] / INTER_SENSOR_DISTANCE
            target_coord[:, 1] -= (NUMOFTAXELS_X - 1)
            target_coord[:, 1] *= -1.0
            ax2.plot(target_coord[:, 0], target_coord[:, 1], 'y*', ms=8)
        plt.pause(0.0001)

        # Visualize estimated from training set
        if scores_val is not None:
            if len(np.shape(scores_val)) == 1:
                scores_val = np.reshape(scores_val, (len(scores_val) / 3, 3))
            target_coord = scores_val[:, :2] / INTER_SENSOR_DISTANCE
            target_coord[:, 1] -= (NUMOFTAXELS_X - 1)
            target_coord[:, 1] *= -1.0
            ax2.plot(target_coord[:, 0], target_coord[:, 1], 'g*', ms=8)

        plt.pause(0.5)


        #targets_raw_z = []
        #for idx in targets_raw: targets_raw_z.append(idx[2])
        #x = np.arange(0,10)
        #ax3.bar(x, targets_raw_z)
        #plt.xticks(x+0.5, ('Head', 'Torso', 'R Elbow', 'L Elbow', 'R Hand', 'L Hand', 'R Knee', 'L Knee', 'R Foot', 'L Foot'), rotation='vertical')
        #plt.title('Distance above Bed')
        #plt.pause(0.0001)

        plt.show()
        #plt.show(block = False)

        return




    def run(self):
        '''Runs either the synthetic database creation script or the
        raw dataset creation script to create a dataset'''
        self.validate_model()
        return





if __name__ == "__main__":

    import optparse
    p = optparse.OptionParser()

    p.add_option('--training_data_path', '--path',  action='store', type='string', \
                 dest='trainingPath',\
                 default='/home/henryclever/hrl_file_server/Autobed/pose_estimation_data/subject_', \
                 help='Set path to the training database.')
    p.add_option('--lab_hd', action='store_true',
                 dest='lab_harddrive', \
                 default=False, \
                 help='Set path to the training database on lab harddrive.')
    p.add_option('--arms_only', action='store_true',
                 dest='arms_only', \
                 default=False, \
                 help='Train only on data from the arms, both sitting and laying.')

    opt, args = p.parse_args()

    PathKey = 'lab_hd'

    if PathKey == 'lab_hd':
        Path = '/media/henryclever/Seagate Backup Plus Drive/Autobed_OFFICIAL_Trials/'
    elif PathKey == 'hc_desktop':
        Path = '/home/henryclever/hrl_file_server/Autobed/'
    else:
        Path = None

    print Path

    #Initialize trainer with a training database file
    p = DataVisualizer(pkl_directory=Path, pathkey = PathKey, opt = opt)
    p.run()
    sys.exit()

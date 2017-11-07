#!/usr/bin/env python
import sys
import os
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.pylab import *

import cPickle as pkl
import random
from scipy import ndimage
import scipy.stats as ss
from scipy.misc import imresize
from scipy.ndimage.interpolation import zoom
from skimage.feature import hog
from skimage import data, color, exposure

from sklearn.cluster import KMeans
from sklearn.preprocessing import scale
from sklearn import svm, linear_model, decomposition, kernel_ridge, neighbors
from sklearn import metrics, cross_validation
from sklearn.utils import shuffle

import convnet_angle as convnet

import pickle
from hrl_lib.util import load_pickle

# Pose Estimation Libraries
from create_dataset_lib import CreateDatasetLib
from synthetic_lib import SyntheticLib
 
#PyTorch libraries
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import transforms
from torch.autograd import Variable



np.set_printoptions(threshold='nan')

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

 
class PhysicalTrainer():
    '''Gets the dictionary of pressure maps from the training database, 
    and will have API to do all sorts of training with it.'''
    def __init__(self, training_database_file, test_file, opt):
        '''Opens the specified pickle files to get the combined dataset:
        This dataset is a dictionary of pressure maps with the corresponding
        3d position and orientation of the markers associated with it.'''
        self.verbose = opt.verbose
        self.opt = opt
        self.synthetic_master = SyntheticLib().synthetic_master

        print test_file
        #Entire pressure dataset with coordinates in world frame


        #we'll be loading this later
        if self.opt.lab_harddrive == True:
            try:
                self.train_val_losses_all = load_pickle('/media/henryclever/Seagate Backup Plus Drive/Autobed_OFFICIAL_Trials/train_val_losses_alldata.p')
            except:
                self.train_val_losses_all = {}
        else:
            try:
                self.train_val_losses_all = load_pickle('/home/henryclever/hrl_file_server/Autobed/train_val_losses_alldata.p')
            except:
                print 'starting anew'
            self.train_val_losses_all = {}



        print 'appending to alldata losses'
        self.train_val_losses_all['train_alldata_flip_shift_scale5_700e_'+str(self.opt.leaveOut)] = []
        self.train_val_losses_all['val_alldata_flip_shift_scale5_700e_'+str(self.opt.leaveOut)] = []
        self.train_val_losses_all['epoch_alldata_flip_shift_scale5_700e_' + str(self.opt.leaveOut)] = []




        #Here we concatenate all subjects in the training database in to one file
        dat = []
        for some_subject in training_database_file:
            print some_subject
            dat_curr = load_pickle(some_subject)
            for inputgoalset in np.arange(len(dat_curr)):
                dat.append(dat_curr[inputgoalset])
        #dat = load_pickle(training_database_file)
        test_dat = load_pickle(test_file)

        print len(dat[8])
        print len(dat), len(test_dat)



       
        #TODO:Write code for the dataset to store these vals
        self.mat_size = (NUMOFTAXELS_X, NUMOFTAXELS_Y)
        self.output_size = (NUMOFOUTPUTNODES, NUMOFOUTPUTDIMS)


        #Randomize the dataset entries
        dat_rand = []
        randentryset = shuffle(np.arange(len(dat)))
        for entry in range(len(dat)):
            dat_rand.append(dat[randentryset[entry]])


        rand_keys = dat
        random.shuffle(rand_keys)
        self.dataset_y = [] #Initialization for the entire dataset

        
        self.train_x_flat = [] #Initialize the training pressure mat list
        for entry in range(len(dat_rand)):
            self.train_x_flat.append(dat_rand[entry][0])
        train_x = self.preprocessing_pressure_array_resize(self.train_x_flat)
        train_x = np.array(train_x)
        self.train_x_tensor = torch.Tensor(train_x)


        self.train_a_flat = [] #Initialize the training pressure mat angle list
        for entry in range(len(dat_rand)):
            self.train_a_flat.append(dat_rand[entry][2])
        train_xa = self.preprocessing_create_pressure_angle_stack(self.train_x_flat, self.train_a_flat)
        train_xa = np.array(train_xa)
        self.train_x_tensor = torch.Tensor(train_xa)


        self.train_y_flat = [] #Initialize the training ground truth list
        for entry in range(len(dat_rand)):
            self.train_y_flat.append(dat_rand[entry][1])
        #train_y = self.preprocessing_output_resize(self.train_y_flat)
        self.train_y_tensor = torch.Tensor(self.train_y_flat)
        self.train_y_tensor = torch.mul(self.train_y_tensor, 1000)




        self.test_x_flat = [] #Initialize the testing pressure mat list
        for entry in range(len(test_dat)):
            self.test_x_flat.append(test_dat[entry][0])
        test_x = self.preprocessing_pressure_array_resize(self.test_x_flat)
        test_x = np.array(test_x)
        self.test_x_tensor = torch.Tensor(test_x)


        self.test_a_flat = []  # Initialize the testing pressure mat angle list
        for entry in range(len(test_dat)):
            self.test_a_flat.append(test_dat[entry][2])
        test_xa = self.preprocessing_create_pressure_angle_stack(self.test_x_flat, self.test_a_flat)
        test_xa = np.array(test_xa)
        self.test_x_tensor = torch.Tensor(test_xa)


        self.test_y_flat = [] #Initialize the ground truth list
        for entry in range(len(test_dat)):
            self.test_y_flat.append(test_dat[entry][1])
        #test_y = self.preprocessing_output_resize(self.test_y_flat)
        self.test_y_tensor = torch.Tensor(self.test_y_flat)
        self.test_y_tensor = torch.mul(self.test_y_tensor, 1000)




        self.dataset_x_flat = self.train_x_flat#Pressure maps
        self.dataset_y = self.train_y_flat
        # [self.dataset_y.append(dat[key]) for key in self.dataset_x_flat]
        self.cv_fold = 3 # Value of k in k-fold cross validation 
        self.mat_frame_joints = []



    def chi2_distance(self, histA, histB, eps = 1e-10):
        # compute the chi-squared distance
        d = 0.5 * np.sum([((a - b) ** 2) / (a + b + eps)
                for (a, b) in zip(histA, histB)])
        # return the chi-squared distance
        return d


    def preprocessing_pressure_array_resize(self, data):
        '''Will resize all elements of the dataset into the dimensions of the 
        pressure map'''
        p_map_dataset = []
        for map_index in range(len(data)):
            #print map_index, self.mat_size, 'mapidx'
            #Resize mat to make into a matrix
            p_map = np.reshape(data[map_index], self.mat_size)
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
            a_map = zeros_like(p_map) + a_data[map_index]


            p_map_dataset.append([p_map, a_map])
        if self.verbose: print len(x_data[0]), 'x', 1, 'size of an incoming pressure map'
        if self.verbose: print len(p_map_dataset[0][0]), 'x', len(p_map_dataset[0][0][0]), 'size of a resized pressure map'
        if self.verbose: print len(p_map_dataset[0][1]), 'x', len(p_map_dataset[0][1][0]), 'size of the stacked angle mat'

        return p_map_dataset


    def preprocessing_output_resize(self, data):

        p_map_dataset = []
        for map_index in range(len(data)):
            #Resize mat to make into a matrix
            p_map = np.reshape(data[map_index], self.output_size)
            p_map_dataset.append(p_map)
        if self.verbose: print len(data[0]),'x',1, 'size of an incoming output'
        if self.verbose: print len(p_map_dataset[0]),'x',len(p_map_dataset[0][0]), 'size of a resized output'
        return p_map_dataset


    def compute_pixel_variance(self, data):
        weight_matrix = np.std(data, axis=0)
        if self.verbose == True: print len(weight_matrix),'x', len(weight_matrix[0]), 'size of weight matrix'
        weight_matrix = weight_matrix/weight_matrix.max()

        x = np.zeros((20, 54))
        y = np.hstack((
                np.hstack((np.ones((60,10)), np.zeros((60, 32)))),
                np.ones((60,12))))
        z = np.ones((48, 54))
        weight_matrix = np.vstack((np.vstack((x,y)), z))
        matshow(weight_matrix, fignum=100, cmap=cm.gray)
        show()
        if self.verbose == True: print len(x),'x', len(x[0]), 'size of x matrix'
        if self.verbose == True: print len(y),'x', len(y[0]), 'size of y matrix'
        if self.verbose == True: print len(z),'x', len(z[0]), 'size of z matrix'
        return weight_matrix


    def find_dataset_deviation(self):
        '''Should return the standard deviation of each joint in the (x,y,z) 
        axis'''
        return np.std(self.dataset_y, axis = 0)


    def convnet_2layer(self):
        #indices = torch.LongTensor([0])
        #self.train_y_tensor = torch.index_select(self.train_y_tensor, 1, indices)

        if self.verbose: print self.train_x_tensor.size(), 'size of the training database'
        if self.verbose: print self.train_y_tensor.size(), 'size of the training database output'
        print self.train_y_tensor
        if self.verbose: print self.test_x_tensor.size(), 'length of the testing dataset'
        if self.verbose: print self.test_y_tensor.size(), 'size of the training database output'



        batch_size = 200
        num_epochs = 700
        hidden_dim = 12
        kernel_size = 10



        #self.train_x_tensor = self.train_x_tensor.unsqueeze(1)
        self.train_dataset = torch.utils.data.TensorDataset(self.train_x_tensor, self.train_y_tensor)
        self.train_loader = torch.utils.data.DataLoader(self.train_dataset, batch_size, shuffle=True)

        #self.test_x_tensor = self.test_x_tensor.unsqueeze(1)
        self.test_dataset = torch.utils.data.TensorDataset(self.test_x_tensor, self.test_y_tensor)
        self.test_loader = torch.utils.data.DataLoader(self.test_dataset, batch_size, shuffle=True)


        self.model = convnet.CNN(self.mat_size, self.output_size, hidden_dim, kernel_size)
        self.criterion = F.cross_entropy
        self.optimizer = optim.SGD(self.model.parameters(), lr=0.00000015, momentum=0.7, weight_decay=0.0005)
        #self.optimizer = optim.RMSprop(self.model.parameters(), lr=0.0000015, momentum=0.7, weight_decay=0.0005)

        # train the model one epoch at a time
        for epoch in range(1, num_epochs + 1):
            self.t1 = time.time()

            self.train(epoch)

            try:
                self.t2 = time.time() - self.t1
            except:
                self.t2 = 0
            print 'Time taken by epoch',epoch,':',self.t2,' seconds'


        #print self.sc
        #print self.tg
        print self.sc - self.tg

        print 'done with epochs, now evaluating'
        self.evaluate('test', verbose=True)

        print self.train_val_losses_all, 'trainval'
        # Save the model (architecture and weights)

        if self.opt.lab_harddrive == True:
            torch.save(self.model, '/media/henryclever/Seagate Backup Plus Drive/Autobed_OFFICIAL_Trials/subject_'+str(self.opt.leaveOut)+'/p_files/convnet_all.pt')
            pkl.dump(self.train_val_losses_all,
                     open(os.path.join('/media/henryclever/Seagate Backup Plus Drive/Autobed_OFFICIAL_Trials/train_val_losses_all.p'), 'wb'))

        else:
            torch.save(self.model, '/home/henryclever/hrl_file_server/Autobed/subject_'+str(self.opt.leaveOut)+'/p_files/convnet_all.pt')
            pkl.dump(self.train_val_losses_all,
                     open(os.path.join('/home/henryclever/hrl_file_server/Autobed/train_val_losses_all.p'), 'wb'))


    def train(self, epoch):
        '''
        Train the model for one epoch.
        '''
        # Some models use slightly different forward passes and train and test
        # time (e.g., any model with Dropout). This puts the model in train mode
        # (as opposed to eval mode) so it knows which one to use.
        self.model.train()
        scores = 0


        #This will loop a total = training_images/batch_size times
        for batch_idx, batch in enumerate(self.train_loader):


            #print batch[0].shape
            batch[0],batch[1] = self.synthetic_master(batch[0], batch[1], flip=True, shift=True, scale=True, bedangle=True)


            sc_last = scores
            images, targets = Variable(batch[0]), Variable(batch[1])


            self.optimizer.zero_grad()

            #print images.size(), 'im size'
            #print targets.size(), 'target size'

            scores = self.model(images)

            #print scores.size(), 'scores'
            self.sc = scores
            self.tg = targets

            #print scores-sc_last

            self.criterion = nn.MSELoss()

            loss = self.criterion(scores,targets)

            loss.backward()
            self.optimizer.step()


            if batch_idx % opt.log_interval == 0:
                self.print_error(self.tg, self.sc, data = 'train')


                self.im_sample = batch[0].numpy()
                self.im_sample = self.im_sample[:,0,:,:]
                self.im_sample = np.squeeze(self.im_sample[0, :])
                self.tar_sample = batch[1].numpy()
                self.tar_sample = np.squeeze(self.tar_sample[0, :])/1000
                self.sc_sample = scores.data.numpy()
                self.sc_sample = np.squeeze(self.sc_sample[0, :]) / 1000
                self.sc_sample = np.reshape(self.sc_sample, self.output_size)



                val_loss = self.evaluate('test', n_batches=4)
                train_loss = loss.data[0]
                examples_this_epoch = batch_idx * len(images)
                epoch_progress = 100. * batch_idx / len(self.train_loader)
                print('Train Epoch: {} [{}/{} ({:.0f}%)]\t'
                      'Train Loss: {:.6f}\tVal Loss: {:.6f}'.format(
                    epoch, examples_this_epoch, len(self.train_loader.dataset),
                    epoch_progress, train_loss, val_loss))


                print 'appending to alldata losses'
                self.train_val_losses_all['train_alldata_flip_shift_scale5_700e_' + str(self.opt.leaveOut)].append(train_loss)
                self.train_val_losses_all['val_alldata_flip_shift_scale5_700e_' + str(self.opt.leaveOut)].append(val_loss)
                self.train_val_losses_all['epoch_alldata_flip_shift_scale5_700e_' + str(self.opt.leaveOut)].append(epoch)




    def evaluate(self, split, verbose=False, n_batches=None):
        '''
        Compute loss on val or test data.
        '''
        #print 'eval', split


        self.model.eval()
        loss = 8.0
        n_examples = 0
        if split == 'val':
            loader = val_loader
        elif split == 'test':
            loader = self.test_loader
        for batch_i, batch in enumerate(loader):
            self.model.train()
            data, target = batch
            #if args.cuda:
            #    data, target = data.cuda(), target.cuda()
            #data, target = Variable(data, volatile=True), Variable(target)
            data, target = Variable(batch[0]), Variable(batch[1])

            output = self.model(data)
            loss += self.criterion(output, target).data[0]


            # predict the argmax of the log-probabilities
            pred = output.data.max(1, keepdim=True)[1]
            n_examples += pred.size(0)

            if n_batches and (batch_i >= n_batches):
                break

        loss /= n_examples
        loss *= 100

        self.print_error(target, output, data='validate')

        self.im_sampleval = data.data.numpy()
        self.im_sampleval = self.im_sampleval[:,0,:,:]
        self.im_sampleval = np.squeeze(self.im_sampleval[0, :])
        self.tar_sampleval = target.data.numpy()
        self.tar_sampleval = np.squeeze(self.tar_sampleval[0, :]) / 1000
        self.sc_sampleval = output.data.numpy()
        self.sc_sampleval = np.squeeze(self.sc_sampleval[0, :]) / 1000
        self.sc_sampleval = np.reshape(self.sc_sampleval, self.output_size)
        self.visualize_pressure_map(self.im_sample, self.tar_sample, self.sc_sample, self.im_sampleval, self.tar_sampleval, self.sc_sampleval)



        if verbose:
            print('\n{} set: Average loss: {:.4f}\n'.format(
                split, loss))
        return loss



    def print_error(self, target, score, data = None):
        error = (score - target)
        error = error.data.numpy()
        error_avg = np.mean(error, axis=0) / 10
        error_avg = np.reshape(error_avg, self.output_size)
        error_avg = np.reshape(np.array(["%.2f" % w for w in error_avg.reshape(error_avg.size)]),
                               self.output_size)
        error_avg = np.transpose(np.concatenate(([['Average Error for Last Batch', '       ', 'Head   ',
                                                   'Torso  ', 'R Elbow', 'L Elbow', 'R Hand ', 'L Hand ',
                                                   'R Knee ', 'L Knee ', 'R Foot ', 'L Foot ']], np.transpose(
            np.concatenate(([['', '', ''], [' x, cm ', ' y, cm ', ' z, cm ']], error_avg))))))
        print data, error_avg

        error_std = np.std(error, axis=0) / 10
        error_std = np.reshape(error_std, self.output_size)
        error_std = np.reshape(np.array(["%.2f" % w for w in error_std.reshape(error_std.size)]),
                               self.output_size)
        error_std = np.transpose(
            np.concatenate(([['Error Standard Deviation for Last Batch', '       ', 'Head   ', 'Torso  ',
                              'R Elbow', 'L Elbow', 'R Hand ', 'L Hand ', 'R Knee ', 'L Knee ',
                              'R Foot ', 'L Foot ']], np.transpose(
                np.concatenate(([['', '', ''], ['x, cm', 'y, cm', 'z, cm']], error_std))))))
        print data, error_std


    def chunks(self, l, n):
        """ Yield successive n-sized chunks from l.
        """
        for i in xrange(0, len(l), n):
            yield l[i:i+n]


    def visualize_pressure_map(self, p_map, targets_raw=None, scores_raw = None, p_map_val = None, targets_val = None, scores_val = None):
        #print p_map.shape, 'pressure mat size', targets_raw.shape, 'target shape'
        #p_map = fliplr(p_map)




        plt.close()
        plt.pause(0.0001)

        fig = plt.figure()
        mngr = plt.get_current_fig_manager()
        # to put it into the upper left corner for example:
        mngr.window.setGeometry(50, 100, 840, 705)

        plt.pause(0.0001)

        # set options
        ax1 = fig.add_subplot(1, 2, 1)
        ax2 = fig.add_subplot(1, 2, 2)


        xlim = [-2.0, 49.0]
        ylim = [86.0, -2.0]
        ax1.set_xlim(xlim)
        ax1.set_ylim(ylim)
        ax2.set_xlim(xlim)
        ax2.set_ylim(ylim)

        # background
        ax1.set_axis_bgcolor('cyan')
        ax2.set_axis_bgcolor('cyan')

        # Visualize pressure maps
        ax1.imshow(p_map, interpolation='nearest', cmap=
        plt.cm.bwr, origin='upper', vmin=0, vmax=100)

        if p_map_val is not None:
            ax2.imshow(p_map_val, interpolation='nearest', cmap=
            plt.cm.bwr, origin='upper', vmin=0, vmax=100)

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
            ax1.plot(target_coord[:, 0], target_coord[:, 1], 'y*', ms=8)

        plt.pause(0.0001)

        #Visualize estimated from training set
        if scores_raw is not None:
            if len(np.shape(scores_raw)) == 1:
                scores_raw = np.reshape(scores_raw, (len(scores_raw) / 3, 3))
            target_coord = scores_raw[:, :2] / INTER_SENSOR_DISTANCE
            target_coord[:, 1] -= (NUMOFTAXELS_X - 1)
            target_coord[:, 1] *= -1.0
            ax1.plot(target_coord[:, 0], target_coord[:, 1], 'g*', ms=8)
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
        ax2.set_title('Validation Sample \n Targets and Estimates')
        plt.pause(0.0001)


        #targets_raw_z = []
        #for idx in targets_raw: targets_raw_z.append(idx[2])
        #x = np.arange(0,10)
        #ax3.bar(x, targets_raw_z)
        #plt.xticks(x+0.5, ('Head', 'Torso', 'R Elbow', 'L Elbow', 'R Hand', 'L Hand', 'R Knee', 'L Knee', 'R Foot', 'L Foot'), rotation='vertical')
        #plt.title('Distance above Bed')
        #plt.pause(0.0001)

        #plt.show()
        plt.show(block = False)

        return



    def person_based_loocv(self):
        '''Computes Person Based Leave One Out Cross Validation. This means
        that if we have 10 participants, we train using 9 participants and test
        on 1 participant, and so on.
        To run this function, make sure that each subject_* directory in the 
        dataset/ directory has a pickle file called individual_database.p
        If you don't have it in some directory that means you haven't run,
        create_raw_database.py on that subject's dataset. So create it and
        ensure that the pkl file is created successfully'''
        #Entire pressure dataset with coordinates in world frame
        dataset_dirname = os.path.dirname(os.path.realpath(training_database_file))
        print dataset_dirname
        subject_dirs = [x[0] for x in os.walk(dataset_dirname)]
        subject_dirs.pop(0)
        print subject_dirs
        dat = []
        for i in range(len(subject_dirs)):
            try:
                dat.append(pkl.load(open(os.path.join(subject_dirs[i],
                    'individual_database.p'), "rb"))) 
            except:
                print "Following dataset directory not formatted correctly. Is there an individual_dataset pkl file for every subject?"
                print os.path.join(subject_dirs[i], 'individual_database.p')
                sys.exit()
        print "Inserted all individual datasets into a list of dicts"
        print "Number of subjects:"
        print len(dat)
        mean_joint_error = np.zeros((len(dat), 10))
        std_joint_error = np.zeros((len(dat), 10))
        for i in range(len(dat)):
            train_dat = {}
            test_dat = dat[i]
            for j in range(len(dat)):
                if j == i:
                    print "#of omitted data points"
                    print len(dat[j].keys())
                    pass
                else:
                    print len(dat[j].keys())
                    print j
                    train_dat.update(dat[j])
            rand_keys = train_dat.keys()
            print "Training Dataset Size:"
            print len(rand_keys)
            print "Testing dataset size:"
            print len(test_dat.keys())
            self.train_y = [] #Initialize the training coordinate list
            self.dataset_y = [] #Initialization for the entire dataset 
            self.train_x_flat = rand_keys[:]#Pressure maps
            [self.train_y.append(train_dat[key]) for key in self.train_x_flat]#Coordinates 
            self.test_x_flat = test_dat.keys()#Pressure maps(test dataset)
            self.test_y = [] #Initialize the ground truth list
            [self.test_y.append(test_dat[key]) for key in self.test_x_flat]#ground truth
            self.dataset_x_flat = rand_keys[:]#Pressure maps
            [self.dataset_y.append(train_dat[key]) for key in self.dataset_x_flat]
            self.cv_fold = 3 # Value of k in k-fold cross validation 
            self.mat_frame_joints = []
            p.train_hog_knn()
            (mean_joint_error[i][:], std_joint_error[i][:]) = self.test_learning_algorithm(self.regr)
            print "Mean Error:"
            print mean_joint_error
        print "MEAN ERROR AFTER PERSON LOOCV:"
        total_mean_error = np.mean(mean_joint_error, axis=0)
        total_std_error = np.mean(std_joint_error, axis=0)
        print total_mean_error
        print "STD DEV:"
        print total_std_error
        pkl.dump(mean_joint_error, open('./dataset/mean_loocv_results.p', 'w'))
        pkl.dump(mean_joint_error, open('./dataset/std_loocv_results.p', 'w'))


if __name__ == "__main__":
    #Initialize trainer with a training database file
    import optparse
    p = optparse.OptionParser()
    p.add_option('--training_dataset', '--train_dataset',  action='store', type='string', \
                 dest='trainPath',\
                 default='/home/henryclever/hrl_file_server/Autobed/pose_estimation_data/basic_train_dataset.p', \
                 help='Specify path to the training database.')
    p.add_option('--leave_out', action='store', type=int, \
                 dest='leaveOut', \
                 help='Specify which subject to leave out for validation')
    p.add_option('--only_test','--t',  action='store_true', dest='only_test',
                 default=False, help='Whether you want only testing of previously stored model')
    p.add_option('--training_model', '--model',  action='store', type='string', \
                 dest='modelPath',\
                 default = '/home/henryclever/hrl_file_server/Autobed/pose_estimation_data', \
                 help='Specify path to the trained model')
    p.add_option('--testing_dataset', '--test_dataset',  action='store', type='string', \
                 dest='testPath',\
                 default='/home/henryclever/hrl_file_server/Autobed/pose_estimation_data/basic_test_dataset.p', \
                 help='Specify path to the training database.')
    p.add_option('--lab_hd', action='store_true',
                 dest='lab_harddrive', \
                 default=False, \
                 help='Set path to the training database on lab harddrive.')
    p.add_option('--verbose', '--v',  action='store_true', dest='verbose',
                 default=False, help='Printout everything (under construction).')
    p.add_option('--log_interval', type=int, default=10, metavar='N',
                        help='number of batches between logging train status')

    opt, args = p.parse_args()

    if opt.lab_harddrive == True:


        opt.subject2Path = '/media/henryclever/Seagate Backup Plus Drive/Autobed_OFFICIAL_Trials/subject_2/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject3Path = '/media/henryclever/Seagate Backup Plus Drive/Autobed_OFFICIAL_Trials/subject_3/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject4Path = '/media/henryclever/Seagate Backup Plus Drive/Autobed_OFFICIAL_Trials/subject_4/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject5Path = '/media/henryclever/Seagate Backup Plus Drive/Autobed_OFFICIAL_Trials/subject_5/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject6Path = '/media/henryclever/Seagate Backup Plus Drive/Autobed_OFFICIAL_Trials/subject_6/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject7Path = '/media/henryclever/Seagate Backup Plus Drive/Autobed_OFFICIAL_Trials/subject_7/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject8Path = '/media/henryclever/Seagate Backup Plus Drive/Autobed_OFFICIAL_Trials/subject_8/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'

        training_database_file = []
    else:

        opt.subject2Path = '/home/henryclever/hrl_file_server/Autobed/subject_2/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject3Path = '/home/henryclever/hrl_file_server/Autobed/subject_3/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject4Path = '/home/henryclever/hrl_file_server/Autobed/subject_4/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject5Path = '/home/henryclever/hrl_file_server/Autobed/subject_5/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject6Path = '/home/henryclever/hrl_file_server/Autobed/subject_6/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject7Path = '/home/henryclever/hrl_file_server/Autobed/subject_7/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject8Path = '/home/henryclever/hrl_file_server/Autobed/subject_8/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject9Path = '/home/henryclever/hrl_file_server/Autobed/subject_9/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject10Path = '/home/henryclever/hrl_file_server/Autobed/subject_10/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject11Path = '/home/henryclever/hrl_file_server/Autobed/subject_11/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject12Path = '/home/henryclever/hrl_file_server/Autobed/subject_12/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject13Path = '/home/henryclever/hrl_file_server/Autobed/subject_13/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject14Path = '/home/henryclever/hrl_file_server/Autobed/subject_14/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject15Path = '/home/henryclever/hrl_file_server/Autobed/subject_15/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject16Path = '/home/henryclever/hrl_file_server/Autobed/subject_16/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject17Path = '/home/henryclever/hrl_file_server/Autobed/subject_17/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'
        opt.subject18Path = '/home/henryclever/hrl_file_server/Autobed/subject_18/p_files/trainval_200rh1_lh1_rl_ll_100rh23_lh23_head_sit120rh_lh_rl_ll.p'

        training_database_file = []





    if opt.leaveOut == 4:
        test_database_file = opt.subject4Path
        #training_database_file.append(opt.subject1Path)
        training_database_file.append(opt.subject2Path)
        training_database_file.append(opt.subject3Path)
        training_database_file.append(opt.subject5Path)
        training_database_file.append(opt.subject6Path)
        training_database_file.append(opt.subject7Path)
        training_database_file.append(opt.subject8Path)

    elif opt.leaveOut == 1:
        test_database_file = opt.subject1Path
        training_database_file.append(opt.subject2Path)
        training_database_file.append(opt.subject3Path)
        training_database_file.append(opt.subject4Path)
        training_database_file.append(opt.subject5Path)
        training_database_file.append(opt.subject6Path)
        training_database_file.append(opt.subject7Path)
        training_database_file.append(opt.subject8Path)

    elif opt.leaveOut == 2:
        test_database_file = opt.subject2Path
        training_database_file.append(opt.subject1Path)
        training_database_file.append(opt.subject3Path)
        training_database_file.append(opt.subject4Path)
        training_database_file.append(opt.subject5Path)
        training_database_file.append(opt.subject6Path)
        training_database_file.append(opt.subject7Path)
        training_database_file.append(opt.subject8Path)

    elif opt.leaveOut == 10:
        test_database_file = opt.subject10Path
        training_database_file.append(opt.subject9Path)
        training_database_file.append(opt.subject11Path)
        training_database_file.append(opt.subject12Path)
        training_database_file.append(opt.subject13Path)
        training_database_file.append(opt.subject14Path)
        training_database_file.append(opt.subject15Path)
        training_database_file.append(opt.subject16Path)
        training_database_file.append(opt.subject17Path)
        training_database_file.append(opt.subject18Path)

    else:
        print 'please specify which subject to leave out for validation using --leave_out _'



    print opt.testPath, 'testpath'
    print opt.modelPath, 'modelpath'



    test_bool = opt.only_test#Whether you want only testing done


    print test_bool, 'test_bool'
    print test_database_file, 'test database file'

    p = PhysicalTrainer(training_database_file, test_database_file, opt)

    if test_bool == True:
        trained_model = load_pickle(opt.modelPath+'/'+training_type+'.p')#Where the trained model is 
        p.test_learning_algorithm(trained_model)
        sys.exit()
    else:
        if opt.verbose == True: print 'Beginning Learning'



        #if training_type == 'convnet_2':
        p.convnet_2layer()

        #else:
        #    print 'Please specify correct training type:1. HoG_KNN 2. convnet_2'

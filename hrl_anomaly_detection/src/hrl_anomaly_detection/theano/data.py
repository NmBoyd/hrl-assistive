import os
import random
import numpy as np
import matplotlib.pyplot as plt
import theano
# By convention, the tensor submodule is loaded as T
import theano.tensor as T

import hrl_lib.util as ut

def getData():

    # Training data - two randomly-generated Gaussian-distributed clouds of points in 2d space
    np.random.seed(0)
    # Number of points
    N = 1000
    # Labels for each cluster
    y = np.random.random_integers(0, 1, N)
    # Mean of each cluster
    means = np.array([[-1, 1], [-1, 1]])
    # Covariance (in X and Y direction) of each cluster
    covariances = np.random.random_sample((2, 2)) + 1
    # Dimensions of each point
    X = np.vstack([np.random.randn(N)*covariances[0, y] + means[0, y],
                   np.random.randn(N)*covariances[1, y] + means[1, y]])
    # Plot the data
    #plt.figure(figsize=(8, 8))
    #plt.scatter(X[0, :], X[1, :], c=y, lw=.3, s=3, cmap=plt.cm.cool)
    #plt.axis([-6, 6, -6, 6])
    #plt.show()
    
    return X, y

def getData2(dataset='./SDA/mnist.pkl.gz'):

    from SDA.logistic_sgd import LogisticRegression, load_data

    datasets = load_data(dataset)

    train_set_x, train_set_y = datasets[0]
    valid_set_x, valid_set_y = datasets[1]
    test_set_x, test_set_y = datasets[2]

    return train_set_x, train_set_y

def getData3(time_window, renew=False):

    from hrl_anomaly_detection import data_manager as dm

    subject_names       = ['gatsbii']
    task                = 'pushing'
    raw_data_path       = os.path.expanduser('~')+'/hrl_file_server/dpark_data/anomaly/RSS2016/'    
    processed_data_path = os.path.expanduser('~')+'/hrl_file_server/dpark_data/anomaly/RSS2016/'+task+'_data'
    save_pkl            = os.path.join(processed_data_path, 'ae_data.pkl')
    ## h5py_file           = os.path.join(processed_data_path, 'test.h5py')
    rf_center           = 'kinEEPos'
    local_range         = 1.25    
    nSet                = 1
    downSampleSize      = 200

    feature_list = ['unimodal_audioPower',\
                    'unimodal_kinVel',\
                    'unimodal_ftForce',\
                    ##'unimodal_visionChange',\
                    ##'unimodal_ppsForce',\
                    ##'unimodal_fabricForce',\
                    'crossmodal_targetEEDist', \
                    'crossmodal_targetEEAng']
    feature_list = ['relativePose_artag_EE', \
                    'relativePose_artag_artag', \
                    'kinectAudio',\
                    'wristAudio', \
                    'ft', \
                    ## 'pps', \
                    ## 'visionChange', \
                    ## 'fabricSkin', \
                    ]

    if os.path.isfile(save_pkl) and renew is not True:
        d = ut.load_pickle(save_pkl)
        new_trainingData = d['trainingData']
        new_testData     = d['testData']

        # Time-sliding window
        new_trainingData2 = getTimeDelayData( new_trainingData, time_window )
        new_testData2     = getTimeDelayData( new_testData, time_window )
        nSingleData       = len(new_testData)-time_window+1

        return new_trainingData2.T, new_testData2.T, nSingleData



    successData, failureData, aug_successData, aug_failureData, param_dict = \
      dm.getDataSet(subject_names, task, raw_data_path, \
                    processed_data_path, rf_center, local_range,\
                    nSet=nSet, \
                    downSampleSize=downSampleSize, \
                    scale=1.0,\
                    ae_data=True, data_ext=False, \
                    feature_list=feature_list, \
                    data_renew=renew)

    # index selection
    success_idx  = range(len(aug_successData[0]))
    failure_idx  = range(len(aug_failureData[0]))

    s_train_idx  = random.sample(success_idx, int( 0.8*len(success_idx)) )
    f_train_idx  = random.sample(failure_idx, int( 0.8*len(failure_idx)) )
    
    s_test_idx = [x for x in success_idx if not x in s_train_idx]
    f_test_idx = [x for x in failure_idx if not x in f_train_idx]

    # data structure: dim x sample x sequence
    normalTrainingData   = aug_successData[:, s_train_idx, :]
    abnormalTrainingData = aug_failureData[:, f_train_idx, :]
    normalTestData       = aug_successData[:, s_test_idx, :]
    abnormalTestData     = aug_failureData[:, f_test_idx, :]

    print "======================================"
    print "Dim x nSamples x nLength"
    print "--------------------------------------"
    print "Normal Train data: ",   np.shape(normalTrainingData)
    print "Abnormal Train data: ", np.shape(abnormalTrainingData)
    print "Normal test data: ",    np.shape(normalTestData)
    print "Abnormal test data: ",  np.shape(abnormalTestData)
    print "======================================"

    # scaling by the number of dimensions in each feature
    dataDim = param_dict['dataDim']
    index   = 0
    for feature_name, nDim in dataDim:
        pre_index = index
        index    += nDim

        normalTrainingData[pre_index:index]   /= np.sqrt(nDim)
        abnormalTrainingData[pre_index:index] /= np.sqrt(nDim)
        normalTestData[pre_index:index]       /= np.sqrt(nDim)
        abnormalTestData[pre_index:index]     /= np.sqrt(nDim)
        

    new_trainingData = np.vstack([np.swapaxes(normalTrainingData, 0, 1), \
                                  np.swapaxes(abnormalTrainingData, 0, 1)])

    new_testData = np.vstack([np.swapaxes(normalTestData, 0, 1),
                              np.swapaxes(abnormalTestData, 0, 1)])
    
    ## new_trainingData = []
    ## for i in xrange(len(trainingData[0])):
    ##     singleSample = []
    ##     for j in xrange(len(trainingData)):
    ##         singleSample.append(trainingData[j][i,:])            
    ##     new_trainingData.append(singleSample)
    
    ## new_testData = []
    ## for i in xrange(len(normalTestData[0])):
    ##     singleSample = []
    ##     for j in xrange(len(normalTestData)):
    ##         singleSample.append(normalTestData[j][i,:])            
    ##     new_testData.append(singleSample)

    ## for i in xrange(len(abnormalTestData[0])):
    ##     singleSample = []
    ##     for j in xrange(len(abnormalTestData)):
    ##         singleSample.append(abnormalTestData[j][i,:])            
    ##     new_testData.append(singleSample)


    print "======================================"
    print "nSamples x Dim x nLength"
    print "--------------------------------------"
    print "Training Data: ", np.shape(new_trainingData)
    print "Test Data: ", np.shape(new_testData)
    print "======================================"

    d = {}        
    d['trainingData'] = new_trainingData
    d['testData']     = new_testData
    ut.save_pickle(d, save_pkl)

    # Time-sliding window
    new_trainingData2 = getTimeDelayData( new_trainingData, time_window )
    new_testData2     = getTimeDelayData( new_testData, time_window )
    nSingleData       = len(new_testData)-time_window+1

    return new_trainingData2.T, new_testData2.T, nSingleData


def getTimeDelayData(data, time_window):

    new_data = []
    for i in xrange(len(data)):
        for j in xrange(len(data[i][0])-time_window+1):
            new_data.append( data[i][:,j:j+time_window].flatten() )

    return np.array(new_data)
    


if __name__ == '__main__':

    
    X_train, X_test, nSingleData = getData3(4, renew=False)

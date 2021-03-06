#!/usr/local/bin/python                                                                                          

# System library
import sys
import os
import time
import math
import numpy as np
import glob
import time

# ROS library
import roslib; roslib.load_manifest('hrl_anomaly_detection') 
import hrl_lib.util as ut
import matplotlib.pyplot as plt
from matplotlib import animation
from matplotlib import gridspec

#
import hrl_lib.circular_buffer as cb
import sandbox_dpark_darpa_m3.lib.hrl_dh_lib as hdl


class anomaly_checker():

    def __init__(self, ml, nDim=1, fXInterval=1.0, fXMax=90.0, sig_mult=1.0, sig_offset=0.0):

        # Object
        self.ml = ml

        # Variables
        self.nFutureStep = self.ml.nFutureStep        
        self.nMaxBuf     = self.ml.nFutureStep
        self.nDim        = nDim        
        self.fXInterval  = fXInterval
        self.fXMax       = fXMax
        self.aXRange     = np.arange(0.0,fXMax,self.fXInterval)
        self.fXTOL       = 1.0e-1
        self.fAnomaly    = self.ml.nFutureStep
        self.sig_mult    = sig_mult
        self.sig_offset  = sig_offset
        
        # 
        self.mu_list = None
        self.var_list = None
        
        pass
        
        
    def update_buffer(self, Y_test):

        # obsrv_range X nFutureStep
        if type(Y_test) == list:
            y = Y_test
        else:
            y = Y_test.tolist()

        self.mu_list, self.var_list = self.ml.multi_step_approximated_predict(y,n_jobs=-1,full_step=True)

        return self.mu_list, self.var_list

        
    def check_anomaly(self, y):
        
        thres_l = self.mu_list + self.sig_mult*np.sqrt(self.var_list) + self.sig_offset
        error = [x for x in thres_l -y if x >= 0.0]

        if y > np.max(thres_l):
            return 1.0, 0.0, 1.0
        else:
            return 0.0, np.mean(error), 0.0

        
    def check_anomaly_batch(self, y, param_list):

        nParam = len(param_list)
        bAnomaly_l = np.zeros(nParam)
        err_l = np.zeros(nParam)

        for i, param in enumerate(param_list):
            sig_mult = param[0]
            sig_offset = param[1]

            thres_l = self.mu_list + sig_mult*self.var_list + sig_offset
            
            if y > np.max(thres_l):
                bAnomaly_l[i] = 1.0
            else:
                err = [x for x in thres_l -y if x >= 0.0]
                err_l[i] = np.mean(err)
            
        return bAnomaly_l, err_l 
                            
        
    def simulation(self, X_test, Y_test):

        mu = np.zeros((len(self.aXRange), self.nFutureStep))
        var = np.zeros((len(self.aXRange), self.nFutureStep))

        plt.rc('text', usetex=True)
        
        self.fig = plt.figure(1)
        self.gs = gridspec.GridSpec(1, 2, width_ratios=[6, 1]) 
        
        self.ax1 = self.fig.add_subplot(self.gs[0])
        self.ax1.set_xlim([0, X_test[-1].max()*1.05])
        self.ax1.set_ylim([0, max(Y_test)*1.4])
        self.ax1.set_xlabel(r'\textbf{Angle [}{^\circ}\textbf{]}', fontsize=22)
        self.ax1.set_ylabel(r'\textbf{Applied Opening Force [N]}', fontsize=22)

        lAll, = self.ax1.plot([], [], color='#66FFFF', lw=2, label='Expected force history')
        line, = self.ax1.plot([], [], lw=2, label='Current force history')
        lmean, = self.ax1.plot([], [], 'm-', linewidth=2.0, label=r'Predicted mean \mu')    
        lvar1, = self.ax1.plot([], [], '--', color='0.75', linewidth=2.0, label=r'Predicted bounds \mu \pm ( d_1 \sigma + d_2 )')    
        lvar2, = self.ax1.plot([], [], '--', color='0.75', linewidth=2.0, )    
        self.ax1.legend(loc=2,prop={'size':12})        

        self.ax2 = self.fig.add_subplot(self.gs[1])        
        lbar,    = self.ax2.bar(0.0001, 0.0, width=1.0, color='b', zorder=1)
        self.ax2.text(0.13, 0.02, 'Normal', fontsize='14', zorder=-1)            
        self.ax2.text(0.05, 0.95, 'Abnormal', fontsize='14', zorder=0)            
        self.ax2.set_xlim([0.0, 1.0])
        self.ax2.set_ylim([0, 1.0])        
        self.ax2.set_xlabel("Anomaly \n Gauge", fontsize=18)        
        ## self.ax2.yaxis.tick_right()
        ## labels = [item.get_text() for item in self.ax2.get_yticklabels()]
        ## for i in xrange(len(labels)): labels[i]=''
        ## labels[0] = 'Normal'
        ## labels[-1] = 'Abnormal'
        ## self.ax2.set_yticklabels(labels)
        plt.setp(self.ax2.get_xticklabels(), visible=False)
        plt.setp(self.ax2.get_yticklabels(), visible=False)
        
        ## res_text = ax.text(0.02, 0.95, '', transform=ax.transAxes)
        ## lbar2, = self.ax1.bar(30.0, 0.0, width=1.0, color='white', edgecolor='k')
        ## lvar , = self.ax1.fill_between([], [], [], facecolor='yellow', alpha=0.5)

        self.fig.subplots_adjust(wspace=0.02)        
        
        def init():
            lAll.set_data([],[])
            line.set_data([],[])
            lmean.set_data([],[])
            lvar1.set_data([],[])
            lvar2.set_data([],[])
            lbar.set_height(0.0)            

            return lAll, line, lmean, lvar1, lvar2, lbar,

        def animate(i):
            lAll.set_data(X_test, Y_test)            
            
            x = X_test[:i]
            y = Y_test[:i]
            x_nxt = X_test[:i+1]
            y_nxt = Y_test[:i+1]
            line.set_data(x, y)
            

            if i > 1:
                mu_list, var_list = self.update_buffer(y)            
                

                ## # check anomaly score
                bFlag, err, fScore = self.check_anomaly(y_nxt[-1])
                
            
            if i >= 3 and i < len(Y_test)-1:# -self.nFutureStep:

                x_sup, idx = hdl.find_nearest(self.aXRange, x[-1], sup=True)            
                a_X   = np.arange(x_sup, x_sup+(self.nFutureStep+1)*self.fXInterval, self.fXInterval)
                
                if x[-1]-x_sup < x[-1]-x[-2]:                    
                    y_idx = 1
                else:
                    y_idx = int((x[-1]-x_sup)/(x[-1]-x[-2]))+1
                a_mu = np.hstack([y[-y_idx], mu_list])
                a_sig = np.hstack([0, np.sqrt(var_list)])

                lmean.set_data( a_X, a_mu)

                ## sig_mult = self.sig_mult*np.arange(self.nFutureStep) + self.sig_offset
                ## sig_mult = np.hstack([0, sig_mult])

                min_val = a_mu - self.sig_mult*a_sig - self.sig_offset
                max_val = a_mu + self.sig_mult*a_sig + self.sig_offset

                lvar1.set_data( a_X, min_val)
                lvar2.set_data( a_X, max_val)
                lbar.set_height(fScore)
                if fScore>=1.0:
                    lbar.set_color('r')
                elif fScore>=0.7:          
                    lbar.set_color('orange')
                else:
                    lbar.set_color('b')
                    
            else:
                lmean.set_data([],[])
                lvar1.set_data([],[])
                lvar2.set_data([],[])
                lbar.set_height(0.0)           

            ## if i>=0 or i<4 : 
            ##     self.ax1.legend(handles=[lAll, line, lmean, lvar1], loc=2,prop={'size':12})        
            ## else:
            ##     self.ax1.legend.set_visible(False)
                                
            ## if i%3 == 0 and i >0:
            ##     plt.savefig('roc_ani_'+str(i)+'.pdf')
                
                
            return lAll, line, lmean, lvar1, lvar2, lbar,

           
        anim = animation.FuncAnimation(self.fig, animate, init_func=init,
                                       frames=len(Y_test), interval=300, blit=True)

        ## anim.save('ani_test.mp4', fps=6, extra_args=['-vcodec', 'libx264'])
        plt.show()

        

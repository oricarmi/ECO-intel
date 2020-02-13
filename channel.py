# -*- coding: utf-8 -*-
"""
Created on Wed Jan 29 10:38:28 2020

@author: Ori
"""

import json 
import numpy as np
import os.path
from scipy import stats as sps
from matplotlib import pyplot as plt
from scipy.stats import norm
import datetime
class channel:
    def __init__(self, numPtsBack,name):
        self.name = name
        self.numPtsBack = numPtsBack
        self.dataTbl = [] # list of values are spectrums
        self.counterTbl = np.zeros((numPtsBack,26))   # binary counters if trend detected or not
        self.timestmps = [] # timestamps of corresponding line in dataTbls/counterTbls
        self.thrshlds = -1*np.ones(26) # thresholds of each frequency and RMS
        self.x = np.arange(numPtsBack) # last numPtsBack points
        self.bslnDist = {'N': 1, 'mu': np.zeros(26), 'signma': np.zeros(26) }
    
    def appendDataLine(self,data,timestmp):
        if datetime.datetime.day(self.timestmps[-1]) == day(timestmp):
            self.dataTbl = self.dataTbl.append(data)
            self.timestmps = self.timestmps(timestmp)
        else:
            self.DayEnd()
            
            
    def kl_divergence(p, q):
        return np.sum(np.where(p != 0, p * np.log(p / q), 0))    
    
    
    def detectTrend(self,freqs):  
        ind = 0 # index for frequencies and RMS ([0,25])
        for k in self.dataTbls.T: # iterate the columns of y and perform linear regression
            if k.size<numPtsBack:
                continue
            slope, intercept, r, p, std_err = sps.linregress(x,np.asarray(k(-self.numPtsBack:-1))) # perform linear regression on last N hours (data tables continues to append until end of day)
            if self.thrshldsTbls[ind]<0: # if hasn't crossed, continue to check against updated mean and std
                Cross = self.predictCrossTime(np.mean(k)+2*np.std(k)) # predict time it will cross threshold if continues in this trend (threshold set as mean of last half hour plus 3*std of last half hour)
            else: # if it crossed, threshold is not -1 and compare to last threshold (last mean+3std that it crossed)
                Cross = self.predictCrossTime(self.thrshldsTbls[ind])
            if Cross>0 and Cross<360 and slope>0: # If it will cross in less than 1 hour (number of 10 seconds in an hour)
                self.counterTbls[:,ind] = np.concatenate((self.counterTbls[1:,ind],[1])) # append 1 to counter
                self.thrshldsTbls[ind] =  np.mean(k)+2*np.std(k) # set threshold to this moment of anomaly
                print("[%s]: %s, %s " % (self.name, self.timestmpsTbls[-1],frqVals[ind]))
            else:
                self.counterTbls[:,ind] = np.concatenate((self.counterTbls[method.routing_key][1:,ind],[0])) # append 0 to counter
                self.thrshldsTbls[ind] =  -1 # reset so that threshold is updated next time it is anomal
            if np.sum(self.counterTbls[-201:-1,ind]) >= 0.8*self.counterTbls[-201:-1].shape[0]: # if in the last N minutes it will cross in less than 1 hour in 80% of the times, alert
                if ind<25: # it is a frequency
                    txtstr = 'trend detected in freq %d [Hz]' %freqs[ind]
                else: # it is the rms
                    txtstr = 'trend detected in RMS'
                self.plotDataAndRegression(k,txtstr,method.routing_key+self.timestmpsTbls[method.routing_key])
                self.counterTbls[method.routing_key][:,ind] = np.zeros(200) # make zeros to not alert many times
                print(txtstr)
            ind+=1  
        
        
    def DayEnd(self):  
        ind = 0
        self.bslnDist['N'] += 1
        for k in self.dataTbls.T: # iterate the rows (25 freqs & RMS) of this channel  
            Mu = np.mean(k)
            Sig = np.std(k)
            rng = np.arange(-10, 10, 0.001)
            KLD = kl_divergence(norm.pdf(rng,self.bslnDist['mu'],self.bslnDist['signma']),norm.pdf(rng, Mu, Sig)) # calculate kullback leibnitz divergence of this day and the previous days
            if KLD<100:
                self.bslnDist['mu'][ind] = ((self.bslnDist['N']-1)*self.bslnDist['mu'][ind]+Mu)/self.bslnDist['N'] # calculate new mean
                self.bslnDist['signma'][ind] = ((self.bslnDist['N']-1)*self.bslnDist['sigma'][ind]+Sig)/self.bslnDist['N'] # calculate new mean std 
            else:
                # send email that day is abnormal
                pass
            ind += 1
        # --- make everything back to zero for new day
        self.dataTbl = []
        self.timestmps = []
        self.counterTbl = np.zeros((self.numPtsBack,26))
        self.thrshlds = -1*np.ones(26)
        
        
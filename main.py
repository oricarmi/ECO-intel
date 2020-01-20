# -*- coding: utf-8 -*-
"""
Created on Fri Jan  3 11:03:06 2020

@author: Ori
"""

import numpy as np
import win32api
from scipy import stats as sps
from matplotlib import pyplot as plt

def linearModel(x):
    return slope*x+intercept
def predictCrossTime(threshold = 3):
    return (threshold - intercept)/slope
def plotData():
    plt.plot(x,y)
    plt.plot(x,list(map(linearModel,x)))
    
    
freqs = [0.5,1,1.5,2,2.5,3.15,4,5,6.3,8,10,12.5,16,20,25,31.5,40,50,63,80,100,125,160,200,250]
counter = np.zeros((30,26),dtype = int) # first 25 are freqs, 26 is energy
x = np.arange(600)
for k in range(counter.shape[1]): # iterate the frequencies
    for i in range(4):
        temp = np.random.normal(i*k/2,1,int(x.size/4))
        if i == 0:
            y = temp
        else:
            y = np.concatenate([y,temp])
    slope, intercept, r, p, std_err = sps.linregress(x, y)
    
    Cross = predictCrossTime(4) 
    if Cross>0 and Cross<360: # If it will cross in less than 1 hour (number of 10 seconds in an hour)
        counter[29,k] +=1
    else:
        counter[29,k] = 0
    if np.sum(counter[:,k]) >= 0.8*counter.shape[0]: # if in the last 5 minutes it will cross in less than 1 hour in 80% of the times
        if k<len(freqs):
            txtstr = 'trend detected in freq %d' %freqs[k]
        else:
            txtstr = 'trend detected in freq total energy'
        win32api.MessageBox(0,txtstr,'alert')
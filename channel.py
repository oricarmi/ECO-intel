# -*- coding: utf-8 -*-
"""
Created on Wed Jan 29 10:38:28 2020

@author: Ori
"""

import pika
import json 
import numpy as np
import win32api
import os.path
from scipy import stats as sps
from matplotlib import pyplot as plt
import smtplib
from email.mime.multipart import MIMEMultipart 
from email.mime.text import MIMEText 
from email.mime.base import MIMEBase 
from email import encoders 

class channel:
    def __init__(self, numPtsBack,name):
        self.name = name
        self.dataTbl = np.zeros((numPtsBack,26)) # dictionary, keys are sensor names and values are spectrums
        self.counterTbl =np.zeros((numPtsBack,26))  # dictionary, keys are sensor names and values are binary counters if trend detected or not
        self.timestmps = [] # dictionary, keys are sensor names and values are timestamps of corresponding line in dataTbls/counterTbls
        self.thrshlds = -1*np.ones(26) #dictionary, keys are sensor names and values are thresholds
    
    def parseInput(self, ch, method, properties, body):
        data = json.loads(body)
        self.timestmpsTbls[method.routing_key].append(data["results"][0]['timestamp']) # get timestamp
        spectrum = data["results"][0]['values'] # get freq values
        freqs = [] # frequencies list
        frqVals = [] # frequencies values list
        for f in spectrum.keys(): # iterate values and make one vector
            try:
                if float(f[0:-2])<=250:
                    freqs.append(float(f[0:-2]))
                    frqVals.append(float(spectrum[f])) 
            except:
                continue
        frqVals = np.asarray(frqVals) # make list to numpy array
        frqVals = np.concatenate((frqVals,[np.sqrt(np.mean(frqVals**2))])) # concatenate rms
        self.dataTbls[method.routing_key] = np.vstack((self.dataTbls[method.routing_key][1:,:],frqVals)) # concatenate new frequencies to already existing
        return freqs,frqVals
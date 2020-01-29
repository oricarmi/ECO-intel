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
    def __init__(self, name, age):
        self.dataTbl = dict() # dictionary, keys are sensor names and values are spectrums
        self.counterTbl = dict()  # dictionary, keys are sensor names and values are binary counters if trend detected or not
        self.timestmps = dict() # dictionary, keys are sensor names and values are timestamps of corresponding line in dataTbls/counterTbls
        self.thrshlds = dict() #dictionary, keys are sensor names and values are thresholds

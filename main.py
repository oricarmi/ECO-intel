# -*- coding: utf-8 -*-
"""
Created on Wed Jan  8 15:08:43 2020

@author: Ori
"""
import pika
import json 
import numpy as np
import os.path
from scipy import stats as sps
from matplotlib import pyplot as plt
from scipy.stats import norm
import smtplib
from email.mime.multipart import MIMEMultipart 
from email.mime.text import MIMEText 
from email.mime.base import MIMEBase 
from email import encoders 
import datetime 

  
def kl_divergence(p, q):
    return np.sum(np.where(p != 0, p * np.log(p / q), 0))    
def predictCrossTime(slope, intercept,threshold):
    return (threshold - intercept)/slope

class channell:
     
    def __init__(self, name,numPtsBack = 1080):
        self.name = name[7:name.find('.V')]
        self.numPtsBack = numPtsBack
        self.dataTbl = [] # list of spectrums (max 8640 x 26)
        self.counterTbl = np.zeros((200,26))   # binary counters if trend detected or not
        self.timestmps = [] # timestamps of corresponding line in dataTbls/counterTbls
        self.thrshlds = -1*np.ones(26) # thresholds of each frequency and RMS
        self.x = np.arange(numPtsBack) # last numPtsBack points
        self.bslnDist = {'N': 1, 'mu': np.zeros(26), 'sigma': np.zeros(26), 'kld': []}
        self.monthly = {'mu': [], 'sigma': []}
    def appendDataLine(self,data,timestmp):
        self.dataTbl.append(data) # append to data tables (of day)
        self.timestmps.append(timestmp) # append to timestamps array
        if len(self.timestmps)>1:
            if (datetime.datetime.date(self.timestmps[-1]) != datetime.datetime.date(self.timestmps[-2])): # if not on the same day
                self.DayEnd() # call day end
            if self.timestmps[-1].month != self.timestmps[-2].month: # if not on the same day
                self.MonthEnd() # call month end
        if len(self.timestmps)>8640: # if more than one day has been appended, remove first line
            self.dataTbl.pop(0)
            self.timestmps.pop(0)
        return
            
    def plotDataAndRegression(self,y,intercept,slope,r,TitlePlt,TitleWord,toSave = 1):
        plt.figure() # plot the vector of numptsback and its regression line
        plt.plot(self.x, y, 'o', label='original data')
        plt.plot(self.x, intercept + slope*self.x, 'r', label='fitted line')
        plt.legend()
        plt.title(TitlePlt + ", " + TitleWord + " ,R-squared: %f" % r**2)
        if toSave:
            plt.savefig(os.path.join(pathImage))
        plt.close()
        sendEmail(TitlePlt + ' @ ' + TitleWord,pathImage) # call function to send email
        append2log(TitleWord) # append anomal event to log
        return

   
    def detectTrend(self):  
        ind = 0 # index for frequencies and RMS ([0,25])
        if len(self.dataTbl)<self.numPtsBack:
            return
        for k in np.asarray(self.dataTbl).T: # iterate the columns of the data and perform linear regression
            kk = k[-self.numPtsBack:]
            slope, intercept, r, p, std_err = sps.linregress(self.x,kk) # perform linear regression on last N hours (data tables continues to append until end of day)
            if self.thrshlds[ind]<0: # if hasn't crossed, continue to check against updated mean and std
                Cross = predictCrossTime(slope, intercept,np.mean(kk)+np.std(kk)) # predict time it will cross threshold if continues in this trend (threshold set as mean of last half hour plus 3*std of last half hour)
            else: # if it crossed, threshold is not -1 and compare to last threshold (last mean+3std that it crossed)
                Cross = predictCrossTime(slope, intercept,self.thrshlds[ind])
            if Cross>0 and Cross<self.numPtsBack/2 and slope>0: # If it will cross in less than 1 hour (number of 10 seconds in an hour)
                self.counterTbl[:,ind] = np.concatenate((self.counterTbl[1:,ind],[1])) # append 1 to counter (of this column (freq or rms))
                self.thrshlds[ind] =  np.mean(kk)+np.std(kk) # set threshold to this moment of anomaly
                if ind<25:
                    print("[%s]: %s, %s " % (self.name, self.timestmps[-1],freqs[ind]))
                else:
                    print("[%s]: %s, RMS " % (self.name, self.timestmps[-1]))
            else:
                self.counterTbl[:,ind] = np.concatenate((self.counterTbl[1:,ind],[0])) # append 0 to counter
                self.thrshlds[ind] =  -1 # reset so that threshold is updated next time it is anomal
            if np.sum(self.counterTbl[:,ind]) >= 0.8*self.counterTbl.shape[0]: # if in the last N minutes it will cross in less than 1 hour in 80% of the times, alert
                if ind<25: # it is a frequency
                    txtstr = 'trend detected in freq %d [Hz]' %freqs[ind]
                else: # it is the rms
                    txtstr = 'trend detected in RMS'
                self.plotDataAndRegression(kk,intercept,slope,r,txtstr,self.name+' '+self.timestmps[-1].strftime("%m/%d/%Y, %H:%M:%S"))
                self.counterTbl[:,ind] = np.zeros(200) # make zeros to not alert many times
                print(txtstr)
            ind+=1  
        return
        
    def DayEnd(self):  
        ind = 0
        self.bslnDist['N'] += 1
        tempM = []
        tempS = []
        rng = np.arange(-10, 10, 0.001)
        for k in np.asarray(self.dataTbl).T: # iterate the rows (25 freqs & RMS) of this channel  
            Mu = np.mean(k)
            Sig = np.std(k)
            tempM.append(Mu)
            tempS.append(Sig)
            if not (self.bslnDist['mu'][ind]==0 and self.bslnDist['sigma'][ind]<0.5): # if not empty the distribution data
                KLD = kl_divergence(norm.pdf(rng,self.bslnDist['mu'][ind],self.bslnDist['sigma'][ind]),norm.pdf(rng, Mu, Sig)) # calculate kullback leibnitz divergence of this day and the baseline distribution
                self.bslnDist['kld'][ind].append(KLD)
                if KLD<150: # if KL divergence is low (dists don't differ much), update baseline distribution
                    self.bslnDist['mu'][ind] = ((self.bslnDist['N']-1)*self.bslnDist['mu'][ind]+Mu)/self.bslnDist['N'] # calculate new mean 
                    self.bslnDist['sigma'][ind] = ((self.bslnDist['N']-1)*self.bslnDist['sigma'][ind]+Sig)/self.bslnDist['N'] # calculate new mean std 
                else: # KL is high and this day's distribution is different than baseline (abnormal)
                    if ind<25:
                        txtstr = self.name + ' day ' + datetime.datetime.date(self.timestmps[-1]).strftime("%m/%d/%Y") + ', freq %d is abnormal' %freqs[ind]
                    else:
                        self.name + ' day ' + datetime.datetime.date(self.timestmps[-1]).strftime("%m/%d/%Y") + ', RMS is abnormal'
                    sendEmail(txtstr,'')# send email that day is abnormal
            else: # it is empty, initialize with this mu and sigma
                self.bslnDist['mu'][ind] = Mu
                self.bslnDist['sigma'][ind] = Sig
            ind+=1
        self.monthly['mu'].append(tempM) # append daily mus of all freqs to monthly
        self.monthly['sigma'].append(tempS) # append daily sigmas of all freqs to monthly
        return
    
    def MonthEnd(self):
        # Call this when a month ends, to trend on the mus and sigmas of all frequencies and RMS of past month, plot data & send email, alert if trend detected during the month                
        ind = 0
        for k1,k2 in np.asarray(self.monthly.mu).T:
            slope, intercept, r, p, std_err = sps.linregress(self.x,k1) # perform linear regression on mus
            if ind<25:
                self.plotDataAndRegression(k1,intercept,slope,r,'Monthly daily averages of ',self.name + freqs[ind] + '[Hz]')
            else:
                self.plotDataAndRegression(k1,intercept,slope,r,'Monthly daily averages of',self.name + 'RMS') 
            slope, intercept, r, p, std_err = sps.linregress(self.x,k2) # perform linear regression on sigmas
            if ind<25:
                self.plotDataAndRegression(k2,intercept,slope,r,'Monthly daily stds of ',self.name + freqs[ind] + '[Hz]')
            else:
                self.plotDataAndRegression(k2,intercept,slope,r,'Monthly daily stds of',self.name + 'RMS') 
            ind = 0
        return
def append2log(TitleWord):
    with open(pathLog, 'a') as file:
        file.write(TitleWord)
    return
def sendEmail(bodyTxt,imgPath):
    gmail_user = 'ecomonitoring2@gmail.com'
    gmail_password = 'monitoring1234'
    to = ['ecomonitoring2@gmail.com'] #'Yair@eco-eng.co.il', 'Amit@eco-eng.co.il',
    msg = MIMEMultipart()    # instance of MIMEMultipart 
    msg['From'] = gmail_user # storing the senders email address       
    msg['To'] = ", ".join(to) # storing the receivers email address  
    msg['Subject'] = "Intel Anomaly Alert!" # storing the subject  
    body = 'Trend Detected - ' + bodyTxt # string to store the body of the mail 
    msg.attach(MIMEText(body, 'plain')) # attach the body with the msg instance 
    filename = 'test.png' 
    try:# try to open the image path and attach to MIME
        attachment = open(imgPath, "rb") # open the file to be sent  
        p = MIMEBase('application', 'octet-stream') # instance of MIMEBase and named as p 
        p.set_payload((attachment).read())  # To change the payload into encoded form 
        encoders.encode_base64(p)  # encode into base64 
        p.add_header('Content-Disposition', "attachment; filename= %s" % filename) 
        msg.attach(p) # attach the instance 'p' to instance 'msg' 
    except: # if didn't succeed, continue to send email without attachment
        pass    
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
#        server.starttls()
        server.login(gmail_user, gmail_password)
        text = msg.as_string() 
        server.sendmail(gmail_user, to, text)
        server.close()
        print('email sent')
    except:
        print('Something went wrong...')
    return

def msg_receive(ch, method, properties, body):
    ######## Parse incoming message #######
    # Sensor name and channel is in the routing key (split on .)
    # print("[%s]: %s " % (method.routing_key, data))
    global channels,freqs,thisChannel
    thisChannel = method.routing_key
    if not thisChannel in channels:
        channels[thisChannel] = channell(thisChannel)
    data = json.loads(body) # parse the body of message received as json object
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
    frqVals.append(np.sqrt(np.mean(np.asarray(frqVals)**2))) # concatenate rms
    channels[thisChannel].appendDataLine(frqVals,datetime.datetime.strptime(data["results"][0]['timestamp'][:-1], '%Y-%m-%dT%H:%M:%S.%f')) # append freq data and timestamp to this channel
    channels[thisChannel].detectTrend()

if __name__ == "__main__":
    pathLog = r'C:\Users\intel\anomaly detection\logfile.txt' #r'C:\Users\Ori\Desktop\Ori\ECO\intel - python\anomaly detection\logfile.txt'#r'C:\Users\user\Desktop\Oric\ECO\intel - python\logfile.txt'
    pathImage = r'C:\Users\intel\anomaly detection\test.png' #r"C:\Users\Ori\Desktop\Ori\ECO\intel - python\anomaly detection\test.png"#r'C:\Users\user\Desktop\Oric\ECO\intel - python\test.png'#
    if not 'channels' in locals():
        channels = dict()
    if not os.path.exists(pathLog):
        open(pathLog, 'w').close()    
    # Setup AMQP Connection
    parameters = pika.URLParameters('amqps://eco-monitoring:p4_HVv%Mb6j&)P@amqp-ext.munisense.net:5671/eco-monitoring')
    parameters.heartbeat = 0
    print("Connecting AMQP..")
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    print("AMQP Connected!")
    print('Starting consume...')
    channel.basic_consume(queue="composite_results_pretty_v1", on_message_callback=msg_receive, auto_ack=True)
    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()
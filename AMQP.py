# -*- coding: utf-8 -*-
"""
Created on Wed Jan  8 15:08:43 2020

@author: Ori
"""
import pika
import json 
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

def msg_receive(ch, method, properties, body):
    ######## Parse incoming message #######
    # Sensor name and channel is in the routing key (split on .)
    # print("[%s]: %s " % (method.routing_key, data))
    global x,dataTbls,sensors
    
    if not method.routing_key in dataTbls:
        dataTbls[method.routing_key] = np.zeros
    data = json.loads(body)
    timestamp = data["results"][0]['timestamp'] # get timestamp
    spectrum = data["results"][0]['values'] # get freq values
    freqs = []
    frqVals = []
    for f in spectrum.keys(): # iterate values and make one vector
        try:
            if float(f[0:-2])<=250:
                freqs.append(float(f[0:-2]))
                frqVals.append(float(spectrum[f])) 
        except:
            continue
    frqVals = np.asarray(frqVals)
    frqVals = np.concatenate((frqVals,[np.sqrt(np.mean(frqVals**2))])) # concatenate rms
    dataTbls[method.routing_key] = np.vstack((frqVals,dataTbls[method.routing_key][0:-1,:])) # concatenate new frequencies to already existing
#    for k in y.T: # iterate the rows of y and perform linear regression
#        slope, intercept, r, p, std_err = sps.linregress(x, y)
#        Cross = predictCrossTime(4) # predict time it will cross threshold if continues in this trend
#        if Cross>0 and Cross<360: # If it will cross in less than 1 hour (number of 10 seconds in an hour)
#            counter[:,k] = np.concatenate(([1], counter[0:-1,k])) 
#        else:
#            counter[:,k] = np.concatenate(([0], counter[0:-1,k])) 
#        if np.sum(counter[:,k]) >= 0.8*counter.shape[0]: # if in the last N minutes it will cross in less than 1 hour in 80% of the times
#            if k<len(freqs):
#                txtstr = 'trend detected in freq %d' %freqs[k]
#            else:
#                txtstr = 'trend detected in RMS'
#            win32api.MessageBox(0,txtstr,'alert')
           

if __name__ == "__main__":
    counter = np.zeros((30,20),dtype = int) # first 19 are freqs, 20 is energy (30 rows, last 5 minutes
    dataTbls = dict()
    sensors = []
    x = np.arange(200) # last 200 points
    # Setup AMQP Connection
    parameters = pika.URLParameters('amqps://eco-monitoring:p4_HVv%Mb6j&)P@amqp-ext.munisense.net:5671/eco-monitoring')

    print("Connecting AMQP..")
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    print("AMQP Connected!")

    print('Starting consume...')
    channel.basic_consume(queue="composite_results_pretty_v1", on_message_callback=msg_receive, auto_ack=True)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()
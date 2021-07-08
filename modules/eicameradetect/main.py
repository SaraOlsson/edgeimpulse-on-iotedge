#!/usr/bin/env python

import asyncio
from pyexpat import features
from xxlimited import Null
import cv2
import os
import sys, getopt
import signal
import time
import json
from edge_impulse_linux.image import ImageImpulseRunner
import numpy as np

from azure.iot.device.aio import IoTHubModuleClient

runner = None
show_camera = False

# global counters
TWIN_CALLBACKS = 0

# module configurations
SCORE_THRESHOLD = 0.5
RUN_CLASSIFICATION = False
FRAME_TICK_MS = 100

# constants
TEST_IMAGE_NAME = "model_test_many.jpg"

def now():
    return round(time.time() * 1000)

def get_webcams():
    port_ids = []
    for port in range(5):
        print("Looking for a camera in port %s:" %port)
        camera = cv2.VideoCapture(port)
        if camera.isOpened():
            ret = camera.read()[0]
            if ret:
                backendName =camera.getBackendName()
                w = camera.get(3)
                h = camera.get(4)
                print("Camera %s (%s x %s) found in port %s " %(backendName,h,w, port))
                port_ids.append(port)
            camera.release()
    return port_ids

def sigint_handler(sig, frame):
    print('Interrupted')
    if (runner):
        runner.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)

def help():
    print('python classify.py <path_to_model.eim> <Camera port ID, only required when more than 1 camera is present>')

def handle_inference_result(res, img, labels):

    list_result = []

    if "classification" in res["result"].keys():
        print('Result (%d ms.) ' % (res['timing']['dsp'] + res['timing']['classification']), end='')
        for label in labels:
            score = res['result']['classification'][label]
            print('%s: %.2f\t' % (label, score), end='')

            if ( score >= SCORE_THRESHOLD):
                dict_result = {
                    "class": label,
                    "score": score
                }
                list_result.append(dict_result)

        print('', flush=True)

        if (show_camera):
            cv2.imshow('edgeimpulse', img)

    elif "bounding_boxes" in res["result"].keys():
        print('Found %d bounding boxes (%d ms.)' % (len(res["result"]["bounding_boxes"]), res['timing']['dsp'] + res['timing']['classification']))
        
        for bb in res["result"]["bounding_boxes"]:
            response = '\t%s (%.2f): x=%d y=%d w=%d h=%d' % (bb['label'], bb['value'], bb['x'], bb['y'], bb['width'], bb['height'])
            print(response)

            score = bb['value']
            # a Python object (dict):
            if ( score >= SCORE_THRESHOLD):
                dict_result = {
                    "class": bb['label'],
                    "score": bb['value'],
                    "rect": {
                        "x": bb['x'],
                        "y": bb['y'],
                        "width": bb['width'],
                        "height": bb['height']
                    }
                }
                list_result.append(dict_result)

        if (show_camera):
            cv2.imshow('edgeimpulse', img)
    
    print('length list_result:', len(list_result))

    #return dict_result
    result = {}
    result["predictions"] = list_result
    return result

async def idle():

    # define behavior for halting the application
    def stdin_listener():
        while True:
            try:
                selection = input("Press Q to quit\n")
                if selection == "Q" or selection == "q":
                    print("Quitting...")
                    break
            except:
                time.sleep(10)

    print ( "The sample is now waiting for messages. ")

    # Run the stdin listener in the event loop
    loop = asyncio.get_event_loop()
    user_finished = loop.run_in_executor(None, stdin_listener)

    # Wait for user to indicate they are done listening for messages
    await user_finished

def get_value_if_exists(property_name, twin_data, default_value):

    value = default_value
    if property_name in twin_data:
        value = twin_data[property_name]
        print(property_name,":", value)
    return value

async def report_properties(module_client, props):
    try:
        await module_client.patch_twin_reported_properties(props)  # blocking call
        print( "The reported properties was updated with: %s" % props)
    except Exception as ex:
        print ( "Unexpected error in report_properties: %s" % ex )

async def twin_patch_listener(module_client):
    global TWIN_CALLBACKS
    global SCORE_THRESHOLD
    global RUN_CLASSIFICATION
    global FRAME_TICK_MS
    print("New twin patch")
    while True:
        try:
            data = await module_client.receive_twin_desired_properties_patch()  # blocking call
            print( "The data in the desired properties patch was: %s" % data)
            SCORE_THRESHOLD = get_value_if_exists("scoreThreshold", data, SCORE_THRESHOLD)
            RUN_CLASSIFICATION = get_value_if_exists("runClassification", data, RUN_CLASSIFICATION)
            FRAME_TICK_MS = get_value_if_exists("frameTickMilliseconds", data, FRAME_TICK_MS)
            TWIN_CALLBACKS += 1
            print ( "Total calls confirmed: %d\n" % TWIN_CALLBACKS )
        except Exception as ex:
            print ( "Unexpected error in twin_patch_listener: %s" % ex )

async def get_twin_initialsettings(module_client):
        global SCORE_THRESHOLD
        global RUN_CLASSIFICATION
        global FRAME_TICK_MS
        print("Will try to get initial twin settings")
        try:
            data = await module_client.get_twin()  # blocking call
            desired_properties = data['desired']
            print( "The INITIAL data in the desired properties was: %s" % data)
            SCORE_THRESHOLD = get_value_if_exists("scoreThreshold", desired_properties, SCORE_THRESHOLD)
            RUN_CLASSIFICATION = get_value_if_exists("runClassification", desired_properties, RUN_CLASSIFICATION)
            FRAME_TICK_MS = get_value_if_exists("frameTickMilliseconds", desired_properties, FRAME_TICK_MS)
        except Exception as ex:
            print ( "Unexpected error in get_twin_initialsettings: %s" % ex )

async def send_json_telemetry(module_client, json_obj):
    json_str = json.dumps(json_obj)
    await module_client.send_message_to_output(json_str, "classification")

async def main(argv):

    try:
        opts, args = getopt.getopt(argv, "h", ["--help"])
    except getopt.GetoptError:
        help()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            help()
            sys.exit()

    if len(args) == 0:
        help()
        sys.exit(2)

    model = args[0]

    dir_path = os.path.dirname(os.path.realpath(__file__))
    modelfile = os.path.join(dir_path, model)

    print('MODEL: ' + modelfile)

    # connect IoT Edge client
    # the client object is used to interact with your Azure IoT hub.
    module_client = IoTHubModuleClient.create_from_edge_environment()
    await module_client.connect()
    # Get inital twin settings
    await get_twin_initialsettings(module_client) 
    # Schedule task for C2D Listener
    listeners = asyncio.gather(twin_patch_listener(module_client))

    # use ML model and read camerastream
    with ImageImpulseRunner(modelfile) as runner:
        try:
            model_info = runner.init()
            print('Loaded runner for "' + model_info['project']['owner'] + ' / ' + model_info['project']['name'] + '"')
            labels = model_info['model_parameters']['labels']
            
            report_props = {'labels': ' '.join(labels)}
            await report_properties(module_client, report_props)
            
            # define device id with argument or search device
            found_camera = False
            if len(args)>= 2:
                videoCaptureDeviceId = int(args[1])
                found_camera = True
            else:
                port_ids = get_webcams()
                if len(port_ids) == 0:
                    print('Cannot find any webcams')
                elif len(args)<= 1 and len(port_ids)> 1:
                    print('Multiple cameras found. Add the camera port ID as a second argument to use to this script')
                else:
                    print('trying with videoCaptureDeviceId anyway?')
                    videoCaptureDeviceId = int(port_ids[0])
                    found_camera = True

            # if no camera, try test image then exit
            if(found_camera == False):
                print("Did not found camera. Use test image")
                image_path = os.path.join(dir_path, TEST_IMAGE_NAME)
                test_image = cv2.imread(image_path)
                features, cropped = runner.get_features_from_image(test_image)
                res = runner.classify(features)
                handled_result = handle_inference_result(res, cropped, labels)

                if handled_result and len(handled_result["predictions"]) > 0:
                    await send_json_telemetry(module_client, handled_result)
                
                print('classification runner response:', res)
                await idle()
                pass
        
            # ready to open video camera (and print info)
            camera = cv2.VideoCapture(videoCaptureDeviceId)
            ret = camera.read()[0]
            if ret:
                backendName = camera.getBackendName()
                w = camera.get(3)
                h = camera.get(4)
                print("Camera %s (%s x %s) in port %s selected." %(backendName,h,w, videoCaptureDeviceId))
                camera.release()
            else:
                raise Exception("Couldn't initialize selected camera.")

            next_frame = 0 # limit to ~10 fps here
            # run classifier (which also capture image)
            if RUN_CLASSIFICATION:
                for res, img in runner.classifier(videoCaptureDeviceId):
                    if (next_frame > now()):
                        time.sleep((next_frame - now()) / 1000)

                    print('classification runner response', res)
                    handled_result = handle_inference_result(res, img, labels)
                    await send_json_telemetry(module_client, handled_result)

                    next_frame = now() + FRAME_TICK_MS
        finally:

            print("Ending program..")
            if (runner):
                runner.stop()
            
            # Cancel listening
            listeners.cancel()

            # Finally, disconnect IoT client
            await module_client.disconnect()


if __name__ == "__main__":

   loop = asyncio.get_event_loop()
   loop.run_until_complete(main(sys.argv[1:]))
   loop.close()

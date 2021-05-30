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
# from azure.iot.device.aio import (IoTHubModuleClient, IoTHubError,
#                            IoTHubMessage,
#                            IoTHubTransportProvider)

runner = None
show_camera = False

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

def get_features(ei_runner, image):

    features = []
    EI_CLASSIFIER_INPUT_WIDTH = ei_runner.dim[0]
    EI_CLASSIFIER_INPUT_HEIGHT = ei_runner.dim[1]
    in_frame_cols = image.shape[1]
    in_frame_rows = image.shape[0]

    print("Test image size: (%s x %s)" %(in_frame_cols,in_frame_rows))

    factor_w = EI_CLASSIFIER_INPUT_WIDTH / in_frame_cols
    factor_h = EI_CLASSIFIER_INPUT_HEIGHT / in_frame_rows
    largest_factor = factor_w if factor_w > factor_h else factor_h

    resize_size_w = int(largest_factor * in_frame_cols)
    resize_size_h = int(largest_factor * in_frame_rows)
    resize_size = (resize_size_w, resize_size_h)

    resized = cv2.resize(image, resize_size, interpolation = cv2.INTER_AREA)

    crop_x = int((resize_size_w - resize_size_h) / 2) if resize_size_w > resize_size_h else 0
    crop_y = int((resize_size_h - resize_size_w) / 2) if resize_size_h > resize_size_w else 0

    crop_region = (crop_x, crop_y, EI_CLASSIFIER_INPUT_WIDTH, EI_CLASSIFIER_INPUT_HEIGHT)

    cropped = resized[crop_region[1]:crop_region[1]+crop_region[3], crop_region[0]:crop_region[0]+crop_region[2]]

    if ei_runner.isGrayscale:
        cropped = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        pixels = np.array(cropped).flatten().tolist()

        for p in pixels:
            features.append((p << 16) + (p << 8) + p)
    else:
        pixels = np.array(cropped).flatten().tolist()

        for ix in range(0, len(pixels), 3):
            b = pixels[ix + 0]
            g = pixels[ix + 1]
            r = pixels[ix + 2]
            features.append((r << 16) + (g << 8) + b)

    return features

async def main(argv):

    global module_client

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

    # ** IoT Edge **
    # The client object is used to interact with your Azure IoT hub.
    module_client = IoTHubModuleClient.create_from_edge_environment()

    # connect the client.
    await module_client.connect()
    # ** IoT Edge end **

    with ImageImpulseRunner(modelfile) as runner:
        try:
            model_info = runner.init()
            print('Loaded runner for "' + model_info['project']['owner'] + ' / ' + model_info['project']['name'] + '"')
            labels = model_info['model_parameters']['labels']
            
            # ***********************************
            test_img = cv2.imread('model_test.jpg', cv2.COLOR_BGR2HSV)
            features = get_features(runner, test_img)
            test_res = runner.classify(features)

            if "bounding_boxes" in test_res["result"].keys():
                    print('Test: Found %d bounding boxes (%d ms.)' % (len(test_res["result"]["bounding_boxes"]), test_res['timing']['dsp'] + test_res['timing']['classification']))
                    for bb in test_res["result"]["bounding_boxes"]:
                        response = '\t%s (%.2f): x=%d y=%d w=%d h=%d' % (bb['label'], bb['value'], bb['x'], bb['y'], bb['width'], bb['height'])
                        print(response)
                        if module_client is not None:
                            #await module_client.send_message(response)
                            await module_client.send_message_to_output(response, "output2")

                            # a Python object (dict):
                            x = {
                                "class": bb['label'],
                                "score": bb['value'],
                                "rect": {
                                    "x": bb['x'],
                                    "y": bb['y'],
                                    "width": bb['width'],
                                    "height": bb['height']
                                }
                            }

                            # convert into JSON:
                            y = json.dumps(x)
                            await module_client.send_message_to_output(y, "classification")

            # ************************************

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

            # Run the stdin listener in the event loop
            print("INFO: run_in_executor...")
            loop = asyncio.get_event_loop()
            user_finished = loop.run_in_executor(None, stdin_listener)

            # Wait for user to indicate they are done listening for messages
            await user_finished

            print("INFO: user_finished...")

            # ********

            if len(args)>= 2:
                videoCaptureDeviceId = int(args[1])
            else:
                port_ids = get_webcams()
                if len(port_ids) == 0:
                    print('Cannot find any webcams')
                    return
                    #raise Exception('Cannot find any webcams')
                if len(args)<= 1 and len(port_ids)> 1:
                    print('Multiple cameras found. Add the camera port ID as a second argument to use to this script')
                    return
                    #raise Exception("Multiple cameras found. Add the camera port ID as a second argument to use to this script")
                videoCaptureDeviceId = int(port_ids[0])

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

            for res, img in runner.classifier(videoCaptureDeviceId):
                if (next_frame > now()):
                    time.sleep((next_frame - now()) / 1000)

                # print('classification runner response', res)

                if "classification" in res["result"].keys():
                    print('Result (%d ms.) ' % (res['timing']['dsp'] + res['timing']['classification']), end='')
                    for label in labels:
                        score = res['result']['classification'][label]
                        print('%s: %.2f\t' % (label, score), end='')
                    print('', flush=True)

                    if (show_camera):
                        cv2.imshow('edgeimpulse', img)
                        if cv2.waitKey(1) == ord('q'):
                            break

                elif "bounding_boxes" in res["result"].keys():
                    print('Found %d bounding boxes (%d ms.)' % (len(res["result"]["bounding_boxes"]), res['timing']['dsp'] + res['timing']['classification']))
                    for bb in res["result"]["bounding_boxes"]:
                        print('\t%s (%.2f): x=%d y=%d w=%d h=%d' % (bb['label'], bb['value'], bb['x'], bb['y'], bb['width'], bb['height']))

                next_frame = now() + 100
        finally:
            if (runner):
                runner.stop()

if __name__ == "__main__":
   #main(sys.argv[1:])

   loop = asyncio.get_event_loop()
   loop.run_until_complete(main(sys.argv[1:]))
   loop.close()
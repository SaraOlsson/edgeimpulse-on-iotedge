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
SCORE_THRESHOLD = 0.5
TWIN_CALLBACKS = 0

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

# if classifying image not from video
# from here: https://github.com/edgeimpulse/linux-sdk-python/blob/master/edge_impulse_linux/image.py
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

    return features, cropped

def handle_inference_result(res, img, labels):

    dict_result = {}

    if "classification" in res["result"].keys():
        print('Result (%d ms.) ' % (res['timing']['dsp'] + res['timing']['classification']), end='')
        for label in labels:
            score = res['result']['classification'][label]
            print('%s: %.2f\t' % (label, score), end='')

            dict_result = {
                "class": label,
                "score": score
            }

        print('', flush=True)

        if (show_camera):
            cv2.imshow('edgeimpulse', img)

    elif "bounding_boxes" in res["result"].keys():
        print('Found %d bounding boxes (%d ms.)' % (len(res["result"]["bounding_boxes"]), res['timing']['dsp'] + res['timing']['classification']))
        for bb in res["result"]["bounding_boxes"]:
            response = '\t%s (%.2f): x=%d y=%d w=%d h=%d' % (bb['label'], bb['value'], bb['x'], bb['y'], bb['width'], bb['height'])
            print(response)

            # a Python object (dict):
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
    
    return dict_result


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
    #print('Run listeners')
    #listeners = await asyncio.gather(twin_patch_listener(module_client))
    #asyncio.run(listeners)

    # use ML model and read camerastream
    with ImageImpulseRunner(modelfile) as runner:
        try:
            model_info = runner.init()
            print('Loaded runner for "' + model_info['project']['owner'] + ' / ' + model_info['project']['name'] + '"')
            labels = model_info['model_parameters']['labels']
            
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
                image_path = os.path.join(dir_path, "model_test.jpg")
                test_image = cv2.imread(image_path)
                features, cropped = get_features(runner, test_image)
                res = runner.classify(features)
                handled_result = handle_inference_result(res, cropped, labels)
                await send_json_telemetry(module_client, handled_result)
                

                print('classification runner response:', res, 'Sleep 5 sec then exit')
                time.sleep(5)
                return
        
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
            for res, img in runner.classifier(videoCaptureDeviceId):
                if (next_frame > now()):
                    time.sleep((next_frame - now()) / 1000)

                print('classification runner response', res)
                handled_result = handle_inference_result(res, img, labels)
                await send_json_telemetry(module_client, handled_result)

                next_frame = now() + 100
        finally:
            if (runner):
                runner.stop()


async def twin_patch_listener(module_client):
        global TWIN_CALLBACKS
        global SCORE_THRESHOLD
        print("in twin_patch_listener")
        while True:
            try:
                data = await module_client.receive_twin_desired_properties_patch()  # blocking call
                print( "The data in the desired properties patch was: %s" % data)
                if "ScoreThreshold" in data:
                    SCORE_THRESHOLD = data["ScoreThreshold"]
                    print("ScoreThreshold", SCORE_THRESHOLD)
                TWIN_CALLBACKS += 1
                print ( "Total calls confirmed: %d\n" % TWIN_CALLBACKS )
            except Exception as ex:
                print ( "Unexpected error in twin_patch_listener: %s" % ex )

if __name__ == "__main__":

   loop = asyncio.get_event_loop()
   loop.run_until_complete(main(sys.argv[1:]))
   loop.close()
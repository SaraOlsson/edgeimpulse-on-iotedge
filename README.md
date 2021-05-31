# edgeimpulse-on-iotedge



- Build TinyML modoel with Edge Impulse
- Learn how to use Linux CLI for Edge Impulse and download model 
- Create an IoT Edge solution in Visual Studio Code
- Create a python application that uses model (Linux Python SDK) and sends telemetry 
- Build Docker image to encapsulate the application and all dependencies
- Prepare Raspberry Pi device to run IoT Edge

<!-- ![header image](media/edgeimpulseXiotedge.png) -->

## Build model with Edge Impulse

note: *This guide focus on object detection, however it can be tweaked to run image classification instead*

For detailed and updated instructions, follow [this guide in the Edge Impulse documentation](https://docs.edgeimpulse.com/docs/object-detection) to create a model for Object Detection. 

![header image](media/create_impulse.png)

## Download model with Linux CLI

We just want to fetch the modelfile, and a way to do it is by installing the [Edge Impulse for Linux CLI](https://docs.edgeimpulse.com/docs/edge-impulse-for-linux) and download model by running the following in the terminal:  
``` $ edge-impulse-linux-runner --download modelfile.eim ```

## Build Docker image

This may be the tricky part, to come up with a Docker file that encapsulate all dependencies for the Azure IoT client, Edge Impulse as well as OpenCV for camera capture and image processing.

I provide a Dockerfile that is validated on a Raspberry Pi 4. Below I provide motivation for various package installations:


From instructions on installing Edge Impulse Linux SDK for Python:

```
$ sudo apt-get install libatlas-base-dev libportaudio0 libportaudio2 libportaudiocpp0 portaudio19-dev 
$ pip3 install edge_impulse_linux -i https://pypi.python.org/simple
 ```

For OpenCV dependencies, I took inspiration from the Azure sample [Custom Vision + Azure IoT Edge on a Raspberry Pi 3](https://github.com/Azure-Samples/Custom-vision-service-iot-edge-raspberry-pi), and in particular [the Dockerfile](https://github.com/Azure-Samples/Custom-vision-service-iot-edge-raspberry-pi/blob/master/modules/CameraCapture/arm32v7.Dockerfile) for the camera capture module. From here I also applied the cross-compilation, but it seems to build and run also without it. 

```
# Required for OpenCV
RUN install_packages \
    # Hierarchical Data Format
    libhdf5-dev libhdf5-serial-dev \
    # for image files
    libjpeg-dev libtiff5-dev libjasper-dev libpng-dev \
    # for video files
    libavcodec-dev libavformat-dev libswscale-dev libv4l-dev \
    # for gui
    libqt4-test libqtgui4 libqtwebkit4 libgtk-3-0 \
    # libgtk2.0-dev eller libgtk-3-dev
    # high def image processing
    libilmbase-dev libopenexr-dev 
```

The next step is to install those Python packages you need in your application, and this step was provided in the original Dockerfile provided by the IoT Edge module template. In addition for the *azure-iot-device* package, I added the [requirements provided](https://github.com/edgeimpulse/linux-sdk-python/blob/master/requirements.txt) in the Edge Impulse repository for Linux SDK Python (sufficient for the image or audio example). You may want to add packages in requirements.txt.

```
COPY requirements.txt ./
RUN pip3 install -r requirements.txt
```

The last ``` COPY . . ``` copies the Python scripts as well as the modelfile.eim to the Docker image

## Prepare Raspberry Pi device to run IoT Edge

First, flash your Raspberry Pi 4 with Raspberry OS to an SD card with your favorite flashing tool, like Raspberry Imager or Balena. Then, prepare the device for headless usage by enabling SSH and setting WIFI credentials (or skip if you'll use an ethernet connection).

Secondly, install dependencies for Edge Impulse. Please follow the instructions in the [documentation guide for Raspberry 4](https://docs.edgeimpulse.com/docs/raspberry-pi-4).

## Running solution

The images below illustrate how the solution may be set up. The website on the laptop screen is the XXX example from. However the resulting telemetry from the module may be used in various way. Learn more about telemetry routing and you can connect your data to custom websites, backend code like serverless Azure Functions etc.
In the Azure IoT Explorer software, it is possible to monitor the incloming telemetry.

![Raspberry Pi](media/raspberry.jpg)
![Raspberry Pi](media/iot_messages.png)
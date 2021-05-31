# edgeimpulse-on-iotedge



- Build TinyML model with Edge Impulse
- Use *Linux CLI for Edge Impulse* and download model 
- Create an IoT Edge solution in Visual Studio Code
- Create a Python application that uses model (Linux Python SDK) and sends telemetry to Azure IoT Hub
- Build Docker image to encapsulate the application and all dependencies
- Prepare Raspberry Pi device to run IoT Edge and deploy solution

### Why IoT Edge?

- deployment at scale, device management
- easy integration with various services (Event Hub, Storage, .. )


<!-- ![header image](media/edgeimpulseXiotedge.png) -->

<!-- Modelfile is about 20 MB. -->

# Build model with Edge Impulse

note: *This guide focus on object detection, however it can be tweaked to run image classification instead*

Sign up for an [account on Edge Impulse](https://studio.edgeimpulse.com/) and choose the option to build a model for object detection.
You can collect data from development boards, from your own devices, or by uploading an existing dataset. Read more about [the data forwarder](https://docs.edgeimpulse.com/docs/cli-data-forwarder) or view the list of fully supported development boards [here](https://docs.edgeimpulse.com/docs/fully-supported-development-boards). 

For detailed and updated instructions, follow [this guide in the Edge Impulse documentation](https://docs.edgeimpulse.com/docs/object-detection) to create a model for Object Detection. 

![header image](media/create_impulse.png)

# Download model with Linux CLI

We just want to fetch the modelfile, and a way to do it is by installing the [Edge Impulse for Linux CLI](https://docs.edgeimpulse.com/docs/edge-impulse-for-linux) and download model by running the following in the terminal:  
``` $ edge-impulse-linux-runner --download modelfile.eim ```

# Create an IoT Edge solution in Visual Studio Code


Install the extension Azure IoT Tools in VS Code.
Run the Command Palette (Ctrl+Shift+P) to easy access the extension commands and search for the option  
 ```Azure IoT Edge: New IoT Edge Solution ```. Pick a location and container registry for your modules* and then you will have the option to create your first module. Pick Python module and you will be provided a template application that listen for messages on the edge broker and forwards them. In short, the deployment template defines what modules should run on the device, what Docker and application settings they have, and how they communicate with each other. Two system modules are always included, and by default there is an example module that publishes simulated temperature data. 
 
 
 *where Azure Container Registry is a convinent option. You may also use localhost for development purpose. Read more about how to use Visual Studio Code to develop and debug modules for Azure IoT Edge [here](https://docs.microsoft.com/en-us/azure/iot-edge/how-to-vs-code-develop-module?view=iotedge-2020-11).

![header image](media/pythonModule.png)

# Create a Python application

![header image](media/pythoncode.png)

# Build Docker image

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

# Prepare Raspberry Pi device to run IoT Edge


First, flash your Raspberry Pi 4 with Raspberry OS to an SD card with your favorite flashing tool, like Raspberry Imager or Balena. Then, prepare the device for headless usage by enabling SSH and setting WIFI credentials (or skip if you'll use an ethernet connection).

Secondly, install dependencies for IoT Edge runtime. Please follow the instructions in the [Microsoft documentation](https://docs.microsoft.com/en-us/azure/iot-edge/how-to-install-iot-edge?view=iotedge-2020-11).

Notes:
- A prerequisite is an Azure account with a free or standard IoT hub in your Azure subscription where you will create a new IoT Edge device.
- The easiest way to authenticate during development is *Option 1: Authenticate with symmetric keys*. That is, you copy the device connection string from your device in Azure IoT Hub to enter in the *config.toml* file in the Provisioning section.

# Running solution

The images below illustrate how the solution may be set up. The website on the laptop screen is the XXX example from. However the resulting telemetry from the module may be used in various way. Learn more about telemetry routing and you can connect your data to custom websites, backend code like serverless Azure Functions etc.
In the Azure IoT Explorer software, it is possible to monitor the incloming telemetry.

![Raspberry Pi](media/raspberry.jpg)
![Raspberry Pi](media/iot_messages.png)
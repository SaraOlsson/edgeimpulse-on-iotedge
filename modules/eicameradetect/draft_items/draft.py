
# NOTE: will remove this file, I'm using it to test classification on a single image not from the camera. 

# ***********************************
# test_img = cv2.imread('model_test.jpg', cv2.COLOR_BGR2HSV)
# features = get_features(runner, test_img)
# test_res = runner.classify(features)

# if "bounding_boxes" in test_res["result"].keys():
#         print('Test: Found %d bounding boxes (%d ms.)' % (len(test_res["result"]["bounding_boxes"]), test_res['timing']['dsp'] + test_res['timing']['classification']))
#         for bb in test_res["result"]["bounding_boxes"]:
#             response = '\t%s (%.2f): x=%d y=%d w=%d h=%d' % (bb['label'], bb['value'], bb['x'], bb['y'], bb['width'], bb['height'])
#             print(response)
#             if module_client is not None:
#                 #await module_client.send_message(response)
#                 await module_client.send_message_to_output(response, "output2")

#                 # a Python object (dict):
#                 x = {
#                     "class": bb['label'],
#                     "score": bb['value'],
#                     "rect": {
#                         "x": bb['x'],
#                         "y": bb['y'],
#                         "width": bb['width'],
#                         "height": bb['height']
#                     }
#                 }

#                 # convert into JSON:
#                 y = json.dumps(x)
#                 await module_client.send_message_to_output(y, "classification")

# #  ... 

# # define behavior for halting the application
# def stdin_listener():
#     while True:
#         try:
#             selection = input("Press Q to quit\n")
#             if selection == "Q" or selection == "q":
#                 print("Quitting...")
#                 break
#         except:
#             time.sleep(10)

# # Run the stdin listener in the event loop
# print("INFO: run_in_executor...")
# loop = asyncio.get_event_loop()
# user_finished = loop.run_in_executor(None, stdin_listener)

# # Wait for user to indicate they are done listening for messages
# await user_finished

# print("INFO: user_finished...")

# # ********
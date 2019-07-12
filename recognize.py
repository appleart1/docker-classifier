import numpy as np
from keras.models import load_model
from keras.preprocessing.image import load_img, img_to_array
from PIL import Image
import subprocess
from subprocess import call
from datetime import datetime
import paho.mqtt.client as mqtt
import sys

import time
import Queue
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from PIL import ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

class Watcher():

    def __init__(self):
        self.observer = Observer()

    def run(self, path):
        q = Queue.LifoQueue(10)
        event_handler = Handler(q=q, ignore_patterns=['/data/detected.jpg', '/data/gate/lastmove.jpg', '*.DS_Store'])

        # load train and test dataset
        def load_data(file):

            image_width = 100
            image_height = 100

            channels = 3
            nb_classes = 11

            imagedata = np.ndarray(shape=(1, image_height, image_width, channels),
                                   dtype=np.float32)
            try:
                img = load_img(file)  # this is a PIL image
            except:
                print("error loading " + file)
            ratio = img.size[0] / img.size[1]
            img = img.resize((int(ratio * image_height), image_height))
            left = int((ratio * image_height - image_width) / 2)
            top = 0
            right = left + image_width
            bottom = image_height

            img = img.crop((left, top, right, bottom))

            # Convert to Numpy Array
            x = img_to_array(img)
            x = x.reshape((image_width, image_height, 3))
            # Normalize
            x = x / 256.0
            imagedata[0] = x

            return imagedata

        # load model
        folder = "/data/gate/"

        model = load_model('/model/model.h5')
        # summarize model.
        # model.summary()

        # classes = ['ania', 'kuba', 'van', 'trash', 'opel', 'night', 'post', 'background']
        classes = ['yes', 'no']

        print("model loaded")
        self.observer.schedule(event_handler, path, recursive=True)
        self.observer.start()
        print("handler started")
        try:
            while True:
                if not q.empty():
                    path = q.get()

                    data = load_data(path)

                    start_time = time.time()
                    # result = model.predict_classes(data)[0]
                    probs = model.predict(data)
                    print("--- prediction: %s ---" % (time.time() - start_time))

                    result = probs.argmax(axis=-1)[0]

                    print(path + ' ' + classes[result])
                    print(probs)

                    if probs[0][result] > 0.90:
                        if classes[result] == 'yes':
                            subprocess.call("cp '" + path + "' /data/gate/lastmove.jpg", shell=True)

                        client = mqtt.Client()
                        client.connect("192.168.1.253", 1883, 60)
                        client.publish("gate/object", classes[result])

                    subprocess.call("mkdir /data/gate/ &> /dev/null" + classes[result], shell=True)
                    subprocess.call("mv '" + path + "' /data/gate/" + classes[result], shell=True)
                else:

                    time.sleep(0.5)
        except KeyboardInterrupt:
            print("stop")
        self.observer.join()


class Handler(PatternMatchingEventHandler):

    def __init__(self, q, ignore_patterns):
        self.q = q
        super(Handler, self).__init__(
            ignore_patterns=ignore_patterns,
            ignore_directories=True
        )

    def on_created(self, event):
        if event.is_directory:
            return None

        # Take any action here when a file is first created.
        path = "%s" % event.src_path
        # print(path)
        self.q.put(path)


if __name__ == '__main__':

    w = Watcher()
    w.run("/data/gate/")


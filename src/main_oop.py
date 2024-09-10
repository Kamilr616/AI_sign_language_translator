#!/usr/bin/env python
# -*- coding: utf-8 -*-
# main_oop.py

__author__ = "Kamil Rataj"
__version__ = "1.0.0"
__maintainer__ = "Kamil Rataj"
__status__ = "Development"

WIN_NAME = "Sign language translator"

import argparse
import sys
import time
import cv2
import mediapipe as mp
#from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2


class GestureRecognizerApp:
    def __init__(self, model: str, num_hands: int, min_hand_detection_confidence: float,
                 min_hand_presence_confidence: float, min_tracking_confidence: float,
                 camera_id: int, width: int, height: int, mirror: bool = False, print_console: bool = False):

        self.print_console = print_console
        self.model = model
        self.num_hands = num_hands
        self.min_hand_detection_confidence = min_hand_detection_confidence
        self.min_hand_presence_confidence = min_hand_presence_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.mirror = mirror

        # Initialize state variables
        self.counter = 0
        self.fps = 0
        self.start_time = time.time()
        self.result_ready = False
        self.recognition_result = None
        self.recognition_frame = None
        self.stop_flag = True

        # MediaPipe drawing and gesture recognizer setup
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

    def save_result(self, result: vision.GestureRecognizerResult, output_image: mp.Image, timestamp_ms: int):
        """Callback to save the recognition result."""
        # Calculate FPS
        if self.counter % 10 == 0:
            self.fps = 10 / (time.time() - self.start_time)
            self.start_time = time.time()

        self.recognition_result = result
        self.counter += 1
        self.result_ready = True
        self.stop_flag = False

    def run(self):
        """Main loop for gesture recognition."""
        cap = cv2.VideoCapture(self.camera_id)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        # Initialize the gesture recognizer model
        base_options = python.BaseOptions(model_asset_path=self.model)
        options = vision.GestureRecognizerOptions(base_options=base_options,
                                                  running_mode=vision.RunningMode.LIVE_STREAM,
                                                  num_hands=self.num_hands,
                                                  min_hand_detection_confidence=self.min_hand_detection_confidence,
                                                  min_hand_presence_confidence=self.min_hand_presence_confidence,
                                                  min_tracking_confidence=self.min_tracking_confidence,
                                                  result_callback=self.save_result)
        recognizer = vision.GestureRecognizer.create_from_options(options)

        print(WIN_NAME.center(150, '-'))

        while cap.isOpened():
            success, image = cap.read()
            if not success:
                sys.exit('ERROR: Unable to read from webcam. Please verify your webcam settings.')

            # Mirror image if necessary
            if self.mirror:
                image = cv2.flip(image, 1)

            if self.stop_flag:
                # Convert image to RGB
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

                # Run gesture recognition asynchronously
                recognizer.recognize_async(mp_image, time.time_ns() // 1_000_000)

            # Display FPS
            fps_text = f'{self.fps:.1f} FPS'
            cv2.putText(image, fps_text, (24, 45), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 0, 0), 1)

            if self.result_ready:
                self.process_recognition_result(image, self.print_console)
                self.result_ready = False

            # Show the frame
            cv2.imshow(WIN_NAME, image if self.recognition_frame is None else self.recognition_frame)

            # Stop the loop if ESC is pressed
            if cv2.waitKey(1) == 27 or cv2.getWindowProperty(WIN_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break

        recognizer.close()
        cap.release()
        cv2.destroyAllWindows()

    def process_recognition_result(self, frame, print_console):
        """Process and display the recognition result."""
        for hand_index, hand_landmarks in enumerate(self.recognition_result.hand_landmarks):
            # Draw landmarks on the frame
            hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
            hand_landmarks_proto.landmark.extend([
                landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in hand_landmarks
            ])
            self.mp_drawing.draw_landmarks(frame, hand_landmarks_proto, self.mp_hands.HAND_CONNECTIONS,
                                           self.mp_drawing_styles.get_default_hand_landmarks_style(),
                                           self.mp_drawing_styles.get_default_hand_connections_style())

            # Display gesture classification result
            if self.recognition_result.gestures:
                gesture = self.recognition_result.gestures[hand_index]
                category_name = gesture[0].category_name
                score = round(gesture[0].score, 3)
                handedness = self.recognition_result.handedness[hand_index]
                handedness_category_name = handedness[0].category_name
                handedness_score = round(handedness[0].score, 3)

                result_text = f'Sign: {category_name} ({format(score, ".1%")})'
                result_text2 = f'Hand: {handedness_category_name} ({format(handedness_score, ".1%")})'

                cv2.putText(frame, result_text, (24, 80), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 0, 255), 2)
                cv2.putText(frame, result_text2, (24, 100), cv2.FONT_HERSHEY_DUPLEX, 0.4, (0, 0, 255), 1)

                if print_console:
                    print(f"{result_text}\n{result_text2}\n")

        self.recognition_frame = frame
        self.stop_flag = True


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--model', help='Name of gesture recognition model.',
                        default='../models/gesture_recognizer_asl_mp.task')
    parser.add_argument('--numHands', help='Max number of hands that can be detected by the recognizer.', default=1,
                        type=int)
    parser.add_argument('--minHandDetectionConfidence',
                        help='The minimum confidence score for hand detection to be considered successful.',
                        default=0.75, type=float)
    parser.add_argument('--minHandPresenceConfidence',
                        help='The minimum confidence score of hand presence score in the hand landmark detection.',
                        default=0.75, type=float)
    parser.add_argument('--minTrackingConfidence',
                        help='The minimum confidence score for the hand tracking to be considered successful.',
                        default=0.75, type=float)
    parser.add_argument('--cameraId', help='Id of camera.', default=0, type=int)
    parser.add_argument('--frameWidth', help='Width of frame to capture from camera.', default=640, type=int)
    parser.add_argument('--frameHeight', help='Height of frame to capture from camera.', default=480, type=int)
    parser.add_argument('--mirrorImage', help='Mirror image: T/F.', default=False, type=bool)
    parser.add_argument('--printConsole', help='Print in console: T/F.', default=False, type=bool)

    args = parser.parse_args()

    app = GestureRecognizerApp(args.model, args.numHands, args.minHandDetectionConfidence,
                               args.minHandPresenceConfidence, args.minTrackingConfidence,
                               args.cameraId, args.frameWidth, args.frameHeight, args.mirrorImage, args.printConsole)
    app.run()


if __name__ == '__main__':
    main()

import cv2
import time
import warnings


class AsyncCamera:
    def __init__(self, **kwargs):
        """
        Initialize the AsyncCamera instance.

        # 0. CV_CAP_PROP_POS_MSEC Current position of the video file in milliseconds.
        # 1. CV_CAP_PROP_POS_FRAMES 0-based index of the frame to be decoded/captured next.
        # 2. CV_CAP_PROP_POS_AVI_RATIO Relative position of the video file
        # 3. CV_CAP_PROP_FRAME_WIDTH Width of the frames in the video stream.
        # 4. CV_CAP_PROP_FRAME_HEIGHT Height of the frames in the video stream.
        # 5. CV_CAP_PROP_FPS Frame rate.
        # 6. CV_CAP_PROP_FOURCC 4-character code of codec.
        # 7. CV_CAP_PROP_FRAME_COUNT Number of frames in the video file.
        # 8. CV_CAP_PROP_FORMAT Format of the Mat objects returned by retrieve() .
        # 9. CV_CAP_PROP_MODE Backend-specific value indicating the current capture mode.
        # 10. CV_CAP_PROP_BRIGHTNESS Brightness of the image (only for cameras).
        # 11. CV_CAP_PROP_CONTRAST Contrast of the image (only for cameras).
        # 12. CV_CAP_PROP_SATURATION Saturation of the image (only for cameras).
        # 13. CV_CAP_PROP_HUE Hue of the image (only for cameras).
        # 14. CV_CAP_PROP_GAIN Gain of the image (only for cameras).
        # 15. CV_CAP_PROP_EXPOSURE Exposure (only for cameras).
        # 16. CV_CAP_PROP_CONVERT_RGB Boolean flags indicating whether images should be converted to RGB.
        # 17. CV_CAP_PROP_WHITE_BALANCE Currently unsupported
        # 18. CV_CAP_PROP_RECTIFICATION Rectification flag for stereo cameras (note: only supported by DC1394 v 2.x backend currently)
        """
        try:
            self.cap = cv2.VideoCapture()
            self.open(kwargs["fd"])
        except Exception:
            warnings.warn("Error while opening the camera")
            self.destroy()
        finally:
            self.configure(**kwargs)

    def settings(self):
        if self.cap:
            self.cap.set(cv2.CAP_PROP_SETTINGS, 1)

    def configure(self, **kwargs):
        try:
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, kwargs["width"])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, kwargs["height"])
            # self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 50)
            # self.cap.set(cv2.CAP_PROP_CONTRAST, 50)
            # self.cap.set(cv2.CAP_PROP_SATURATION, 50)
            # self.cap.set(cv2.CAP_PROP_HUE, 0)
            # self.cap.set(cv2.CAP_PROP_AUTO_WB, 1)
            #self.cap.set(cv2.CAP_PROP_SETTINGS, 1)
        except Exception:
            warnings.warn("Error while configuring the camera")
            self.destroy()

    def open(self, fd):
        try:
            self.cap.open(fd, cv2.CAP_DSHOW)
        except Exception:
            warnings.warn("Error while opening the camera")
            self.destroy()

    def destroy(self):
        if self.cap.isOpened():
            self.cap.release()
            self.cap = None

    def is_ended(self):
        return not self.cap.isOpened()

    def read(self):
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                return frame[..., ::-1]
            else:
                return None

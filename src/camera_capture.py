import queue
import threading
import cv2
import time
import warnings


class AsyncCamera:
    def __init__(self, fd=1, **kwargs):
        """
        Initialize the AsyncCamera instance.

        Args:
            fd (int): File descriptor for the camera. Defaults to 1.
            **kwargs: Additional keyword arguments to set camera properties.
        """
        # Set attributes from kwargs
        for k in kwargs:
            setattr(self, k, kwargs[k])

        # Convert specific attributes to integers
        def s_int(s, k1):
            setattr(s, k1, int(getattr(s, k1)))

        s_int(self, "fps")
        s_int(self, "width")
        s_int(self, "height")

        # Initialize queues for frame processing
        self.q = queue.Queue()
        self.q2 = queue.Queue()

        # Start the camera capture thread
        self.t = threading.Thread(target=AsyncCamera.func, args=(
        self.q, self.q2, fd, {"fps": self.fps, "width": self.width, "height": self.height, "format": self.format}))
        self.t.start()
        self.current = None

    def destroy(self):
        """
        Signal the capture thread to stop.
        """
        self.q2.put(0)
        self.t.join()

    def is_ended(self):
        """
        Check if the capture has ended.
        Returns:
            bool: Returns False if thread has ended.
        """
        if not self.t.is_alive():
            return True
        else:
            return False

    @staticmethod
    def func(q, q2, fd, opt):
        """
        Capture frames from the camera and put them into the queue.

        Args:
            q (queue.Queue): Queue to put captured frames.
            q2 (queue.Queue): Queue to receive stop signal.
            fd (int): File descriptor for the camera.
            opt (dict): Dictionary of camera options.
        """
        try:
            # Open the video capture with the given file descriptor
            v = cv2.VideoCapture(fd)
            # Set video capture properties
            v.set(cv2.CAP_PROP_FOURCC,
                  (ord(opt['format'][0]) << 0) + (ord(opt['format'][1]) << 8) + (ord(opt['format'][2]) << 16) + (
                              ord(opt['format'][3]) << 24))
            v.set(cv2.CAP_PROP_FPS, opt["fps"])
            v.set(cv2.CAP_PROP_FRAME_WIDTH, opt["width"])
            v.set(cv2.CAP_PROP_FRAME_HEIGHT, opt["height"])

            while v.isOpened():
                if not q2.empty():
                    return
                # Read a frame from the video capture
                stat, src = v.read()
                if stat:
                    if q.empty():
                        src = cv2.cvtColor(src, cv2.COLOR_BGR2RGB)
                        q.put((time.time_ns(), src))
        except Exception as e:
            warnings.warn(f"Exception in camera capture: {e}")

    def read(self):
        """
        Read a frame from the queue.

        Returns:
            tuple: The latest frame from the queue.
        """
        while self.current is None:
            if not self.q.empty():
                self.current = self.q.get()
        if not self.q.empty():
            self.current = self.q.get()
        return self.current

from typing import Mapping, Tuple
from mediapipe.python.solutions import hands_connections
from mediapipe.python.solutions.drawing_utils import DrawingSpec
from mediapipe.python.solutions.hands import HandLandmark

# Constants for drawing specifications
_RADIUS = 5
_RADIUS_2 = 7

_RED = (255, 0, 0)
_GREEN = (8, 180, 8)
_BLUE = (0, 0, 255)
_LIME = (50, 250, 50)
_SKY_BLUE = (28, 140, 255)

# Thickness for different parts of the hand
_THICKNESS_WRIST_MCP = 2
_THICKNESS_FINGER = 3
_THICKNESS_DOT = - 1

# Hand landmarks grouped by parts of the hand
_PALM_LANDMARKS = (HandLandmark.WRIST, HandLandmark.THUMB_CMC,
                   HandLandmark.INDEX_FINGER_MCP,
                   HandLandmark.MIDDLE_FINGER_MCP, HandLandmark.RING_FINGER_MCP,
                   HandLandmark.PINKY_MCP)

_FINGER_LANDMARKS = (HandLandmark.THUMB_MCP,
                     HandLandmark.THUMB_IP,
                     HandLandmark.PINKY_PIP,
                     HandLandmark.PINKY_DIP,
                     HandLandmark.INDEX_FINGER_PIP,
                     HandLandmark.INDEX_FINGER_DIP,
                     HandLandmark.MIDDLE_FINGER_PIP,
                     HandLandmark.MIDDLE_FINGER_DIP,
                     HandLandmark.RING_FINGER_PIP,
                     HandLandmark.RING_FINGER_DIP)

_FINGER_TIPS = (
HandLandmark.THUMB_TIP, HandLandmark.INDEX_FINGER_TIP, HandLandmark.MIDDLE_FINGER_TIP, HandLandmark.RING_FINGER_TIP,
HandLandmark.PINKY_TIP)

# Drawing specifications for each part of the hand
_HAND_LANDMARK_STYLE = {
    _PALM_LANDMARKS:
        DrawingSpec(
            color=_GREEN, thickness=_THICKNESS_DOT, circle_radius=_RADIUS),
    _FINGER_LANDMARKS:
        DrawingSpec(
            color=_LIME, thickness=_THICKNESS_DOT, circle_radius=_RADIUS),
    _FINGER_TIPS:
        DrawingSpec(
            color=_RED, thickness=_THICKNESS_DOT, circle_radius=_RADIUS_2)
}

# Drawing specifications for connections between hand landmarks
_HAND_CONNECTION_STYLE = {
    hands_connections.HAND_PALM_CONNECTIONS:
        DrawingSpec(color=_BLUE, thickness=_THICKNESS_WRIST_MCP),
    hands_connections.HAND_THUMB_CONNECTIONS:
        DrawingSpec(color=_SKY_BLUE, thickness=_THICKNESS_FINGER),
    hands_connections.HAND_INDEX_FINGER_CONNECTIONS:
        DrawingSpec(color=_SKY_BLUE, thickness=_THICKNESS_FINGER),
    hands_connections.HAND_MIDDLE_FINGER_CONNECTIONS:
        DrawingSpec(color=_SKY_BLUE, thickness=_THICKNESS_FINGER),
    hands_connections.HAND_RING_FINGER_CONNECTIONS:
        DrawingSpec(color=_SKY_BLUE, thickness=_THICKNESS_FINGER),
    hands_connections.HAND_PINKY_FINGER_CONNECTIONS:
        DrawingSpec(color=_SKY_BLUE, thickness=_THICKNESS_FINGER)
}


def get_hand_landmarks_style() -> Mapping[int, DrawingSpec]:
    """
    Returns the hand landmarks drawing style.

    Returns:
        Mapping[int, DrawingSpec]: A mapping from each hand landmark to its drawing spec.
    """
    hand_landmark_style = {}
    for k, v in _HAND_LANDMARK_STYLE.items():
        for landmark in k:
            hand_landmark_style[landmark] = v
    return hand_landmark_style


def get_hand_connections_style() -> Mapping[Tuple[int, int], DrawingSpec]:
    """
    Returns the hand connections drawing style.

    Returns:
        Mapping[Tuple[int, int], DrawingSpec]: A mapping from each hand connection to its drawing spec.
    """
    hand_connection_style = {}
    for k, v in _HAND_CONNECTION_STYLE.items():
        for connection in k:
            hand_connection_style[connection] = v
    return hand_connection_style

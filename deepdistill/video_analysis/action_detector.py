"""
人物 / 动作识别
使用 MediaPipe 检测视频中的人体姿态，分析动作类型。
当 MediaPipe 不可用时，降级为基于 OpenCV 的简易人脸/运动检测。
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("deepdistill.video_analysis.action")


def detect_actions(file_path: Path, scenes: list[dict]) -> list[dict]:
    """
    对每个场景的关键帧进行人物/动作检测。

    Returns:
        动作列表：
        - scene_id: 场景编号
        - person_count: 检测到的人数
        - poses: 姿态信息列表
        - action_type: 推断的动作类型
    """
    try:
        import mediapipe as mp
        return _mediapipe_detect(file_path, scenes)
    except ImportError:
        logger.warning("MediaPipe 未安装，使用 OpenCV 简易检测")
        return _opencv_detect(file_path, scenes)


def _mediapipe_detect(file_path: Path, scenes: list[dict]) -> list[dict]:
    """使用 MediaPipe Pose 进行人体姿态检测"""
    import mediapipe as mp

    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        static_image_mode=True,
        model_complexity=1,
        min_detection_confidence=0.5,
    )

    cap = cv2.VideoCapture(str(file_path))
    results_list = []

    for scene in scenes:
        mid_frame = (scene["start_frame"] + scene["end_frame"]) // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
        ret, frame = cap.read()
        if not ret:
            continue

        # MediaPipe 需要 RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_results = pose.process(rgb_frame)

        poses = []
        person_count = 0
        action_type = "无人物"

        if mp_results.pose_landmarks:
            person_count = 1  # Pose 模型单人检测
            landmarks = mp_results.pose_landmarks.landmark

            # 提取关键关节位置
            key_joints = {
                "nose": _get_landmark(landmarks, mp_pose.PoseLandmark.NOSE),
                "left_shoulder": _get_landmark(landmarks, mp_pose.PoseLandmark.LEFT_SHOULDER),
                "right_shoulder": _get_landmark(landmarks, mp_pose.PoseLandmark.RIGHT_SHOULDER),
                "left_elbow": _get_landmark(landmarks, mp_pose.PoseLandmark.LEFT_ELBOW),
                "right_elbow": _get_landmark(landmarks, mp_pose.PoseLandmark.RIGHT_ELBOW),
                "left_wrist": _get_landmark(landmarks, mp_pose.PoseLandmark.LEFT_WRIST),
                "right_wrist": _get_landmark(landmarks, mp_pose.PoseLandmark.RIGHT_WRIST),
                "left_hip": _get_landmark(landmarks, mp_pose.PoseLandmark.LEFT_HIP),
                "right_hip": _get_landmark(landmarks, mp_pose.PoseLandmark.RIGHT_HIP),
            }
            poses.append(key_joints)

            # 推断动作类型
            action_type = _infer_action(landmarks, mp_pose.PoseLandmark)

        results_list.append({
            "scene_id": scene["scene_id"],
            "person_count": person_count,
            "poses": poses,
            "action_type": action_type,
        })

    cap.release()
    pose.close()
    return results_list


def _get_landmark(landmarks, landmark_enum) -> dict:
    """提取单个关节点坐标"""
    lm = landmarks[landmark_enum.value]
    return {
        "x": round(lm.x, 4),
        "y": round(lm.y, 4),
        "visibility": round(lm.visibility, 3),
    }


def _infer_action(landmarks, PoseLandmark) -> str:
    """
    基于关节位置推断动作类型。
    简易规则：根据手臂/身体相对位置判断。
    """
    nose = landmarks[PoseLandmark.NOSE.value]
    l_wrist = landmarks[PoseLandmark.LEFT_WRIST.value]
    r_wrist = landmarks[PoseLandmark.RIGHT_WRIST.value]
    l_shoulder = landmarks[PoseLandmark.LEFT_SHOULDER.value]
    r_shoulder = landmarks[PoseLandmark.RIGHT_SHOULDER.value]
    l_hip = landmarks[PoseLandmark.LEFT_HIP.value]
    r_hip = landmarks[PoseLandmark.RIGHT_HIP.value]
    l_knee = landmarks[PoseLandmark.LEFT_KNEE.value]
    r_knee = landmarks[PoseLandmark.RIGHT_KNEE.value]

    # 双手举过头顶
    if l_wrist.y < l_shoulder.y and r_wrist.y < r_shoulder.y:
        return "举手/欢呼"

    # 单手举起（可能在演讲/指向）
    if l_wrist.y < l_shoulder.y or r_wrist.y < r_shoulder.y:
        return "手势/指向"

    # 身体弯曲（髋关节和肩膀接近）
    shoulder_y = (l_shoulder.y + r_shoulder.y) / 2
    hip_y = (l_hip.y + r_hip.y) / 2
    if abs(shoulder_y - hip_y) < 0.1:
        return "弯腰/俯身"

    # 坐姿（膝盖弯曲，髋关节位置较低）
    knee_y = (l_knee.y + r_knee.y) / 2
    if hip_y > 0.5 and knee_y > hip_y:
        return "坐姿"

    # 默认站立
    return "站立"


def _opencv_detect(file_path: Path, scenes: list[dict]) -> list[dict]:
    """
    OpenCV 简易检测（MediaPipe 不可用时的 fallback）。
    使用 Haar 级联检测人脸，帧间差异检测运动。
    """
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    cap = cv2.VideoCapture(str(file_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    results_list = []

    for scene in scenes:
        mid_frame = (scene["start_frame"] + scene["end_frame"]) // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 人脸检测
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        person_count = len(faces)

        # 运动检测（比较前后帧）
        motion_level = "静止"
        start_f = max(0, mid_frame - int(fps))
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
        ret1, frame1 = cap.read()
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
        ret2, frame2 = cap.read()

        if ret1 and ret2:
            diff = cv2.absdiff(
                cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY),
                cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY),
            )
            motion_score = float(np.mean(diff))
            if motion_score > 20:
                motion_level = "剧烈运动"
            elif motion_score > 8:
                motion_level = "轻微运动"

        action_type = f"{person_count}人, {motion_level}" if person_count > 0 else f"无人物, {motion_level}"

        results_list.append({
            "scene_id": scene["scene_id"],
            "person_count": person_count,
            "poses": [],
            "action_type": action_type,
        })

    cap.release()
    return results_list

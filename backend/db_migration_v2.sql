-- 기존 DB가 이미 존재하는 경우에만 검토 후 적용하세요.
-- 새 DB라면 init_db.py가 ORM 기준으로 테이블을 생성합니다.

-- User_Profile은 User와 1:1 관계여야 합니다.
ALTER TABLE User_Profile
    ADD UNIQUE KEY uq_user_profile_user_id (user_id);

-- 아래 조건 마스터 데이터는 중복 삽입하지 않도록 확인합니다.
INSERT INTO Condition_Master (condition_code, condition_name, description)
VALUES
('AVOID_STAIRS', '계단 제외', '계단이 포함된 이동 구간을 제외합니다.'),
('PREFER_ELEVATOR', '엘리베이터 경유', '가능하면 엘리베이터를 사용하는 경로를 우선합니다.'),
('AVOID_STEEP_INCLINE', '급경사 제외', '허용 경사도를 초과하는 구간을 제외합니다.'),
('NEED_LOW_BUS', '저상버스 필요', '버스 이용 시 저상버스 확인 경로를 우선/필수로 적용합니다.'),
('AVOID_OBSTACLE_STEP', '보도 턱 제외', '허용 높이를 초과하는 보도 턱 구간을 제외합니다.'),
('AVOID_GENERAL_BUS', '일반 버스 제외', '일반 버스가 포함된 경로를 제외합니다.')
ON DUPLICATE KEY UPDATE
condition_name = VALUES(condition_name),
description = VALUES(description);

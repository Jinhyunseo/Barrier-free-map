-- ============================================================
-- 성남시 교통약자 길안내
-- 2차 프로토타입 DB v2
-- MySQL Server 9.x / MySQL Workbench 8.x 호환용
--
-- 목적
-- 1. 지하철 역사 기준정보
-- 2. 역사 내 엘리베이터/에스컬레이터 시설정보
-- 3. 시설 현재 상태 및 상태 변경 이력
-- 4. 성남시 버스정류장 기준정보
-- 5. 사용자 현장 사진 제보
-- 6. AI 사진 검증 결과
-- ============================================================

-- 주의:
-- 이 스크립트는 기존 seongnam_nav_db 데이터베이스를 삭제하고
-- 새로 생성합니다.
-- 기존 데이터가 필요하다면 실행하지 마세요.

DROP DATABASE IF EXISTS `seongnam_nav_db`;

CREATE DATABASE `seongnam_nav_db`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE `seongnam_nav_db`;


-- ============================================================
-- 1. User
-- ============================================================

CREATE TABLE `User` (
    `user_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `email` VARCHAR(100) NOT NULL,
    `password_hash` VARCHAR(255) NOT NULL,
    `nickname` VARCHAR(50) NOT NULL,

    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (`user_id`),
    UNIQUE KEY `uk_user_email` (`email`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='사용자';


-- ============================================================
-- 2. Station
-- 지하철 역사 기준정보
-- ============================================================

CREATE TABLE `Station` (
    `station_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,

    `operator_code` VARCHAR(30) NULL
        COMMENT '철도 운영기관 코드',

    `line_code` VARCHAR(30) NULL
        COMMENT '노선 코드',

    `line_name` VARCHAR(100) NULL
        COMMENT '노선명',

    `station_code` VARCHAR(50) NOT NULL
        COMMENT '공공데이터 역사 코드',

    `station_name` VARCHAR(100) NOT NULL
        COMMENT '역사명',

    `latitude` DECIMAL(10,7) NULL,
    `longitude` DECIMAL(11,7) NULL,

    `data_source` VARCHAR(50) NOT NULL DEFAULT 'PUBLIC_JSON',

    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (`station_id`),

    UNIQUE KEY `uk_station_identity`
        (`operator_code`, `line_code`, `station_code`),

    KEY `idx_station_name` (`station_name`),
    KEY `idx_station_code` (`station_code`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='지하철 역사 기준정보';


-- ============================================================
-- 3. Facility
-- 역사 내부 이동시설
-- ELEVATOR / ESCALATOR
-- ============================================================

CREATE TABLE `Facility` (
    `facility_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,

    `station_id` INT UNSIGNED NOT NULL,

    `facility_type` VARCHAR(30) NOT NULL
        COMMENT 'ELEVATOR / ESCALATOR',

    `facility_name` VARCHAR(100) NULL,

    `external_facility_code` VARCHAR(100) NULL
        COMMENT '공공데이터 시설 식별자',

    `exit_no` VARCHAR(20) NULL
        COMMENT '출입구 번호',

    `direction` VARCHAR(30) NULL,

    `detail_location` TEXT NULL
        COMMENT '상세 위치',

    `from_floor_name` VARCHAR(30) NULL,
    `to_floor_name` VARCHAR(30) NULL,

    `from_floor` DECIMAL(5,2) NULL,
    `to_floor` DECIMAL(5,2) NULL,

    `passenger_capacity` INT NULL,
    `weight_capacity_kg` INT NULL,

    `latitude` DECIMAL(10,7) NULL,
    `longitude` DECIMAL(11,7) NULL,

    `data_source` VARCHAR(50) NOT NULL DEFAULT 'PUBLIC_JSON',

    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (`facility_id`),

    CONSTRAINT `fk_facility_station`
        FOREIGN KEY (`station_id`)
        REFERENCES `Station` (`station_id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    KEY `idx_facility_station` (`station_id`),
    KEY `idx_facility_type` (`facility_type`),
    KEY `idx_facility_external_code` (`external_facility_code`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='역사 내부 이동시설';


-- ============================================================
-- 4. Facility_Status
-- 시설의 현재 상태
--
-- NORMAL
-- BROKEN
-- INSPECTION
-- UNKNOWN
-- ============================================================

CREATE TABLE `Facility_Status` (
    `status_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    `facility_id` INT UNSIGNED NOT NULL,

    `status_code` VARCHAR(30) NOT NULL DEFAULT 'NORMAL',

    `is_usable` TINYINT(1) NOT NULL DEFAULT 1,

    `is_usable_wheelchair` TINYINT(1) NOT NULL DEFAULT 1,

    `source_type` VARCHAR(30) NOT NULL DEFAULT 'INITIAL_DATA',

    `source_report_id` BIGINT UNSIGNED NULL,

    `last_updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (`status_id`),

    UNIQUE KEY `uk_facility_current_status`
        (`facility_id`),

    KEY `idx_status_code` (`status_code`),
    KEY `idx_status_updated` (`last_updated_at`),
    KEY `idx_status_source_report` (`source_report_id`),

    CONSTRAINT `fk_status_facility`
        FOREIGN KEY (`facility_id`)
        REFERENCES `Facility` (`facility_id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='시설 현재 이용상태';


-- ============================================================
-- 5. Facility_Status_History
-- 시설 상태 변경 이력
-- ============================================================

CREATE TABLE `Facility_Status_History` (
    `history_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    `facility_id` INT UNSIGNED NOT NULL,

    `previous_status` VARCHAR(30) NULL,
    `new_status` VARCHAR(30) NOT NULL,

    `source_type` VARCHAR(30) NOT NULL,

    `report_id` BIGINT UNSIGNED NULL,

    `confidence_score` DECIMAL(5,2) NULL,

    `changed_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (`history_id`),

    KEY `idx_history_facility` (`facility_id`),
    KEY `idx_history_report` (`report_id`),
    KEY `idx_history_changed_at` (`changed_at`),

    CONSTRAINT `fk_history_facility`
        FOREIGN KEY (`facility_id`)
        REFERENCES `Facility` (`facility_id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='시설 상태 변경 이력';


-- ============================================================
-- 6. Bus_Stop
-- 성남시 버스정류장 기준정보
-- ============================================================

CREATE TABLE `Bus_Stop` (
    `bus_stop_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,

    `stop_code` VARCHAR(30) NOT NULL
        COMMENT '정류장 번호',

    `stop_name` VARCHAR(150) NOT NULL
        COMMENT '정류장명',

    `detail_location` VARCHAR(255) NULL,

    `latitude` DECIMAL(10,7) NOT NULL,
    `longitude` DECIMAL(11,7) NOT NULL,

    `district` VARCHAR(50) NULL,
    `administrative_dong` VARCHAR(100) NULL,

    `stop_installation_type` VARCHAR(50) NULL,
    `central_lane` CHAR(1) NULL,
    `chair_type` VARCHAR(50) NULL,
    `bit_type` VARCHAR(100) NULL,

    `air_cleaner_installed` CHAR(1) NULL,
    `heating_cooling_installed` CHAR(1) NULL,
    `windshield_installed` CHAR(1) NULL,
    `fine_dust_sensor_installed` CHAR(1) NULL,
    `emergency_bell_installed` CHAR(1) NULL,
    `wifi_installed` CHAR(1) NULL,
    `red_zone` CHAR(1) NULL,

    `city_bus_routes` TEXT NULL,
    `intercity_bus_routes` TEXT NULL,

    `data_source` VARCHAR(50) NOT NULL DEFAULT 'PUBLIC_JSON',

    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (`bus_stop_id`),

    UNIQUE KEY `uk_bus_stop_code` (`stop_code`),

    KEY `idx_bus_stop_name` (`stop_name`),
    KEY `idx_bus_stop_location` (`latitude`, `longitude`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='성남시 버스정류장 기준정보';


-- ============================================================
-- 7. User_Report
-- 사용자 현장 제보
-- ============================================================

CREATE TABLE `User_Report` (
    `report_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    `user_id` INT UNSIGNED NOT NULL,

    `facility_id` INT UNSIGNED NULL,
    `bus_stop_id` INT UNSIGNED NULL,

    `report_type` VARCHAR(30) NOT NULL,

    `title` VARCHAR(150) NOT NULL,
    `description` TEXT NULL,

    `image_url` VARCHAR(500) NULL,

    `latitude` DECIMAL(10,7) NOT NULL,
    `longitude` DECIMAL(11,7) NOT NULL,

    `report_status` VARCHAR(20) NOT NULL DEFAULT 'PENDING',

    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (`report_id`),

    CONSTRAINT `fk_report_user`
        FOREIGN KEY (`user_id`)
        REFERENCES `User` (`user_id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT `fk_report_facility`
        FOREIGN KEY (`facility_id`)
        REFERENCES `Facility` (`facility_id`)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    CONSTRAINT `fk_report_bus_stop`
        FOREIGN KEY (`bus_stop_id`)
        REFERENCES `Bus_Stop` (`bus_stop_id`)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    KEY `idx_report_user` (`user_id`),
    KEY `idx_report_facility` (`facility_id`),
    KEY `idx_report_bus_stop` (`bus_stop_id`),
    KEY `idx_report_status` (`report_status`),
    KEY `idx_report_created_at` (`created_at`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='사용자 현장 제보';


-- ============================================================
-- 8. AI_Verification
-- AI 사진 검증 결과
-- ============================================================

CREATE TABLE `AI_Verification` (
    `verification_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    `report_id` BIGINT UNSIGNED NOT NULL,

    `place_match` TINYINT(1) NOT NULL DEFAULT 0,
    `facility_match` TINYINT(1) NOT NULL DEFAULT 0,
    `state_match` TINYINT(1) NOT NULL DEFAULT 0,

    `confidence_score` DECIMAL(5,2) NULL,

    `verification_result` VARCHAR(20) NOT NULL DEFAULT 'PENDING',

    `reason` TEXT NULL,

    `model_name` VARCHAR(100) NULL,

    `raw_response` JSON NULL,

    `verified_at` DATETIME NULL,

    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (`verification_id`),

    UNIQUE KEY `uk_verification_report`
        (`report_id`),

    CONSTRAINT `fk_verification_report`
        FOREIGN KEY (`report_id`)
        REFERENCES `User_Report` (`report_id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    KEY `idx_verification_result` (`verification_result`),
    KEY `idx_verification_confidence` (`confidence_score`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='사용자 사진 AI 검증 결과';


-- ============================================================
-- 9. 시설 현재 상태 조회용 View
-- ============================================================

CREATE VIEW `v_facility_current_status` AS
SELECT
    f.facility_id,
    s.station_id,
    s.station_name,
    s.line_name,
    f.facility_type,
    f.facility_name,
    f.external_facility_code,
    f.exit_no,
    f.detail_location,
    fs.status_code,
    fs.is_usable,
    fs.is_usable_wheelchair,
    fs.source_type,
    fs.last_updated_at
FROM `Facility` AS f
INNER JOIN `Station` AS s
    ON s.station_id = f.station_id
LEFT JOIN `Facility_Status` AS fs
    ON fs.facility_id = f.facility_id;


-- ============================================================
-- 10. 생성 결과 확인
-- ============================================================

SHOW TABLES;

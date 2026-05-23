-- =====================================================
-- SCHOLARIO 2.0 — Database Schema + Demo Seed Data
-- SRMIST CSE · Sem 4 · DBMS Project
-- =====================================================
-- HOW TO RUN:
--   Open MySQL command line and run:
--   source C:/path/to/schema.sql
--   OR from terminal:
--   mysql -u root -p < schema.sql
-- =====================================================

DROP DATABASE IF EXISTS scholario;
CREATE DATABASE scholario;
USE scholario;

-- ── TABLES ────────────────────────────────────────

CREATE TABLE users (
  user_id     INT AUTO_INCREMENT PRIMARY KEY,
  reg_number  VARCHAR(20) UNIQUE NOT NULL,
  name        VARCHAR(100) NOT NULL,
  email       VARCHAR(100) UNIQUE NOT NULL,
  password    VARCHAR(255) NOT NULL,
  role        ENUM('student','faculty','admin') NOT NULL DEFAULT 'student',
  last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE class (
  class_id   INT AUTO_INCREMENT PRIMARY KEY,
  class_name VARCHAR(50) NOT NULL,
  subject    VARCHAR(100) NOT NULL,
  faculty_id INT NOT NULL,
  semester   INT DEFAULT 4,
  section    VARCHAR(10) DEFAULT 'AL2',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE student (
  student_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT UNIQUE NOT NULL,
  class_id   INT NOT NULL,
  reg_number VARCHAR(20) UNIQUE NOT NULL,
  section    VARCHAR(10) DEFAULT 'AL2',
  FOREIGN KEY (user_id)  REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (class_id) REFERENCES class(class_id)
);

CREATE TABLE teacher (
  teacher_id  INT AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNIQUE NOT NULL,
  department  VARCHAR(100) DEFAULT 'Computer Science & Engineering',
  designation VARCHAR(100) DEFAULT 'Assistant Professor',
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE assignment (
  assignment_id INT AUTO_INCREMENT PRIMARY KEY,
  class_id      INT NOT NULL,
  faculty_id    INT NOT NULL,
  title         VARCHAR(200) NOT NULL,
  description   TEXT,
  difficulty    ENUM('Easy','Medium','Hard') DEFAULT 'Medium',
  due_date      DATETIME NOT NULL,
  max_marks     INT DEFAULT 10,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (class_id)   REFERENCES class(class_id),
  FOREIGN KEY (faculty_id) REFERENCES users(user_id)
);

CREATE TABLE submission (
  submission_id   INT AUTO_INCREMENT PRIMARY KEY,
  assignment_id   INT NOT NULL,
  student_id      INT NOT NULL,
  submission_text TEXT,
  submitted_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  status          ENUM('submitted','checked','pending') DEFAULT 'submitted',
  marks_obtained  INT DEFAULT NULL,
  is_late         BOOLEAN DEFAULT FALSE,
  penalty_pct     INT DEFAULT 0,
  effective_marks INT DEFAULT NULL,
  plagiarism_flag BOOLEAN DEFAULT FALSE,
  plagiarism_note VARCHAR(255) DEFAULT NULL,
  FOREIGN KEY (assignment_id) REFERENCES assignment(assignment_id),
  FOREIGN KEY (student_id)    REFERENCES student(student_id)
);

CREATE TABLE remark (
  remark_id     INT AUTO_INCREMENT PRIMARY KEY,
  submission_id INT NOT NULL,
  faculty_id    INT NOT NULL,
  remark_text   TEXT NOT NULL,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (submission_id) REFERENCES submission(submission_id),
  FOREIGN KEY (faculty_id)    REFERENCES users(user_id)
);

CREATE TABLE attendance (
  attendance_id INT AUTO_INCREMENT PRIMARY KEY,
  student_id    INT NOT NULL,
  class_id      INT NOT NULL,
  date          DATE NOT NULL,
  status        ENUM('present','absent','late') DEFAULT 'present',
  marked_by     INT,
  UNIQUE KEY uq_att (student_id, class_id, date),
  FOREIGN KEY (student_id) REFERENCES student(student_id),
  FOREIGN KEY (class_id)   REFERENCES class(class_id)
);

CREATE TABLE notification (
  notif_id   INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT NOT NULL,
  title      VARCHAR(200) NOT NULL,
  message    TEXT,
  type       ENUM('info','warning','success','urgent') DEFAULT 'info',
  is_read    BOOLEAN DEFAULT FALSE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE audit_log (
  log_id     INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT,
  action     VARCHAR(100) NOT NULL,
  details    TEXT,
  ip_address VARCHAR(45),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE at_risk (
  risk_id    INT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL,
  reason     VARCHAR(255) NOT NULL,
  att_pct    DECIMAL(5,2),
  sub_rate   DECIMAL(5,2),
  flagged_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  resolved   BOOLEAN DEFAULT FALSE,
  FOREIGN KEY (student_id) REFERENCES student(student_id)
);

-- ── SEED DATA ──────────────────────────────────────

INSERT INTO users VALUES (1,'ADMIN001','Administrator','admin@scholario.edu','admin123','admin',NOW(),NOW());

INSERT INTO users VALUES
(2,'FAC001','Dr. Priya Sharma','faculty1@scholario.edu','faculty123','faculty',NOW(),NOW()),
(3,'FAC002','Dr. Rajesh Kumar','faculty2@scholario.edu','faculty123','faculty',NOW(),NOW()),
(4,'FAC003','Prof. Meena Iyer','faculty3@scholario.edu','faculty123','faculty',NOW(),NOW());

INSERT INTO teacher(user_id,department,designation) VALUES
(2,'Computer Science & Engineering','Associate Professor'),
(3,'Computer Science & Engineering','Assistant Professor'),
(4,'Computer Science & Engineering','Professor');

INSERT INTO class(class_id,class_name,subject,faculty_id,semester,section) VALUES
(1,'CSE-A','Database Management Systems',2,4,'AL2'),
(2,'CSE-A','Data Structures & Algorithms',3,4,'AL2'),
(3,'CSE-A','Operating Systems',4,4,'AL2');

-- 20 demo students (no real names or emails)
INSERT INTO users(reg_number,name,email,password,role) VALUES
('RA2411033010001','Alex Johnson','alex.j@scholario.edu','pass123','student'),
('RA2411033010002','Jamie Smith','jamie.s@scholario.edu','pass123','student'),
('RA2411033010003','Casey Brown','casey.b@scholario.edu','pass123','student'),
('RA2411033010004','Morgan Davis','morgan.d@scholario.edu','pass123','student'),
('RA2411033010005','Riley Wilson','riley.w@scholario.edu','pass123','student'),
('RA2411033010006','Taylor Moore','taylor.m@scholario.edu','pass123','student'),
('RA2411033010007','Jordan Taylor','jordan.t@scholario.edu','pass123','student'),
('RA2411033010008','Quinn Anderson','quinn.a@scholario.edu','pass123','student'),
('RA2411033010009','Avery Thomas','avery.t@scholario.edu','pass123','student'),
('RA2411033010010','Reese Jackson','reese.j@scholario.edu','pass123','student'),
('RA2411033010011','Blake White','blake.w@scholario.edu','pass123','student'),
('RA2411033010012','Drew Harris','drew.h@scholario.edu','pass123','student'),
('RA2411033010013','Skyler Martin','skyler.m@scholario.edu','pass123','student'),
('RA2411033010014','Peyton Garcia','peyton.g@scholario.edu','pass123','student'),
('RA2411033010015','Emery Lee','emery.l@scholario.edu','pass123','student'),
('RA2411033010016','Sage Robinson','sage.r@scholario.edu','pass123','student'),
('RA2411033010017','River Clark','river.c@scholario.edu','pass123','student'),
('RA2411033010018','Phoenix Lewis','phoenix.l@scholario.edu','pass123','student'),
('RA2411033010019','Dakota Hall','dakota.h@scholario.edu','pass123','student'),
('RA2411033010020','Finley Allen','finley.a@scholario.edu','pass123','student');

INSERT INTO student(user_id,class_id,reg_number,section)
SELECT user_id,1,reg_number,'AL2' FROM users WHERE role='student';

INSERT INTO assignment(class_id,faculty_id,title,description,difficulty,due_date,max_marks,created_at) VALUES
(1,2,'ER Diagram Design','Design a complete ER diagram for a hospital management system','Medium',DATE_ADD(NOW(),INTERVAL 7 DAY),10,DATE_SUB(NOW(),INTERVAL 7 DAY)),
(1,2,'SQL Queries — DML','Write DML queries covering INSERT, UPDATE, DELETE with constraints','Easy',DATE_ADD(NOW(),INTERVAL 14 DAY),10,DATE_SUB(NOW(),INTERVAL 3 DAY)),
(2,3,'Sorting Algorithms','Implement and compare Bubble, Merge, and Quick Sort','Hard',DATE_ADD(NOW(),INTERVAL 5 DAY),15,DATE_SUB(NOW(),INTERVAL 10 DAY)),
(3,4,'Process Scheduling','Compare FCFS, SJF and Round Robin scheduling with examples','Hard',DATE_ADD(NOW(),INTERVAL 3 DAY),15,DATE_SUB(NOW(),INTERVAL 8 DAY));

-- Submissions (mix of on-time, late, plagiarised)
INSERT INTO submission(assignment_id,student_id,submission_text,submitted_at,status,marks_obtained,is_late,penalty_pct,effective_marks,plagiarism_flag,plagiarism_note) VALUES
(1,1,'ER diagram covers Patient, Doctor, Ward, Appointment entities. PKs and FKs defined. Cardinalities: Doctor treats Patient (1:N), Patient books Appointment (1:1).',DATE_SUB(NOW(),INTERVAL 3 DAY),'checked',8,FALSE,0,8,FALSE,NULL),
(1,2,'Hospital ER: entities Patient, Doctor, Department, Appointment. Relationships defined with proper cardinalities and participation constraints.',DATE_SUB(NOW(),INTERVAL 3 DAY),'checked',7,FALSE,0,7,FALSE,NULL),
(1,3,'Hospital ER: entities Patient, Doctor, Department, Appointment. Relationships defined with proper cardinalities and participation constraints.',DATE_SUB(NOW(),INTERVAL 1 DAY),'checked',5,TRUE,10,5,TRUE,'High text similarity (91%) detected with another submission'),
(1,4,'Full ER with Patient, Doctor, Nurse, Ward, Bed, Medication. Weak entity Prescription depends on Appointment entity.',DATE_SUB(NOW(),INTERVAL 4 DAY),'checked',9,FALSE,0,9,FALSE,NULL),
(1,5,'ER diagram: Patient (PatientID PK, Name, DOB), Doctor (DoctorID PK, Specialization), Appointment (AppID PK, Date, Time).',DATE_SUB(NOW(),INTERVAL 2 DAY),'checked',6,FALSE,0,6,FALSE,NULL),
(3,1,'Bubble O(n²) space O(1). Merge O(nlogn) space O(n) stable. Quick O(nlogn) avg O(n²) worst. Implemented all three in C.',DATE_SUB(NOW(),INTERVAL 5 DAY),'checked',13,FALSE,0,13,FALSE,NULL),
(3,2,'Sorting comparison: Bubble simple but slow, Merge best for linked lists, Quick fastest in practice due to cache performance.',DATE_SUB(NOW(),INTERVAL 5 DAY),'checked',11,FALSE,0,11,FALSE,NULL),
(3,6,'Bubble O(n²) space O(1). Merge O(nlogn) space O(n) stable. Quick O(nlogn) avg O(n²) worst. Implemented all three in C.',DATE_SUB(NOW(),INTERVAL 5 DAY),'submitted',NULL,FALSE,0,NULL,TRUE,'High text similarity (95%) detected with another submission');

INSERT INTO remark(submission_id,faculty_id,remark_text,created_at) VALUES
(1,2,'Good ER diagram. Well defined entities and relationships. Could add Prescription as weak entity.',DATE_SUB(NOW(),INTERVAL 2 DAY)),
(2,2,'Decent work. Cardinalities need more detail. Missing participation constraints.',DATE_SUB(NOW(),INTERVAL 2 DAY)),
(4,2,'Excellent! Complete ER with all entities and proper notation. Very well done.',DATE_SUB(NOW(),INTERVAL 2 DAY)),
(6,3,'Perfect implementation with complexity analysis. Great work.',DATE_SUB(NOW(),INTERVAL 4 DAY)),
(7,3,'Good comparison. Could elaborate on cache performance differences.',DATE_SUB(NOW(),INTERVAL 4 DAY));

-- Attendance last 30 weekdays (students 1-15, varied patterns)
DELIMITER $$
CREATE PROCEDURE seed_attendance()
BEGIN
  DECLARE i INT DEFAULT 1;
  DECLARE d DATE;
  WHILE i <= 15 DO
    SET d = DATE_SUB(CURDATE(), INTERVAL 41 DAY);
    WHILE d <= CURDATE() DO
      IF DAYOFWEEK(d) NOT IN (1,7) THEN
        INSERT IGNORE INTO attendance(student_id,class_id,date,status,marked_by) VALUES(
          i, 1, d,
          CASE
            WHEN i IN (13,14,15) THEN IF(RAND()<0.45,'present','absent')
            WHEN i IN (1,4)      THEN 'present'
            ELSE IF(RAND()<0.84,'present', IF(RAND()<0.4,'late','absent'))
          END, 2
        );
      END IF;
      SET d = DATE_ADD(d, INTERVAL 1 DAY);
    END WHILE;
    SET i = i + 1;
  END WHILE;
END$$
DELIMITER ;
CALL seed_attendance();
DROP PROCEDURE seed_attendance;

-- At-risk auto-detect
INSERT INTO at_risk(student_id, reason, att_pct, sub_rate)
SELECT st.student_id,
  CONCAT('Attendance ', ROUND(SUM(a.status IN ('present','late'))*100.0/NULLIF(COUNT(*),0),1), '% below 75% threshold'),
  ROUND(SUM(a.status IN ('present','late'))*100.0/NULLIF(COUNT(*),0),1), 0
FROM student st
JOIN attendance a ON a.student_id=st.student_id
GROUP BY st.student_id
HAVING ROUND(SUM(a.status IN ('present','late'))*100.0/NULLIF(COUNT(*),0),1) < 75;

-- Notifications
INSERT INTO notification(user_id,title,message,type,is_read,created_at) VALUES
(7,'Assignment Graded','Your ER Diagram submission has been graded. Score: 8/10','success',FALSE,NOW()),
(7,'New Assignment Posted','SQL Queries — DML assignment posted. Due in 14 days.','info',FALSE,DATE_SUB(NOW(),INTERVAL 1 DAY)),
(7,'Attendance Warning','Your DBMS attendance is approaching 75%. Attend regularly.','warning',FALSE,DATE_SUB(NOW(),INTERVAL 2 DAY)),
(2,'⚠ Plagiarism Alert','Similarity detected between 2 submissions for ER Diagram','urgent',FALSE,NOW()),
(2,'New Submission','Student submitted ER Diagram assignment','info',FALSE,DATE_SUB(NOW(),INTERVAL 1 DAY)),
(1,'At-Risk Report','3 students flagged below 75% attendance threshold','urgent',FALSE,NOW());

-- Audit log
INSERT INTO audit_log(user_id,action,details,ip_address,created_at) VALUES
(1,'LOGIN','Admin logged in','127.0.0.1',DATE_SUB(NOW(),INTERVAL 3 HOUR)),
(2,'LOGIN','Faculty Dr. Priya Sharma logged in','127.0.0.1',DATE_SUB(NOW(),INTERVAL 2 HOUR)),
(2,'GRADE','Graded submission #1 — 8/10','127.0.0.1',DATE_SUB(NOW(),INTERVAL 100 MINUTE)),
(2,'GRADE','Graded submission #2 — 7/10','127.0.0.1',DATE_SUB(NOW(),INTERVAL 90 MINUTE)),
(2,'CREATE_ASSIGNMENT','Created: SQL Queries — DML','127.0.0.1',DATE_SUB(NOW(),INTERVAL 80 MINUTE)),
(7,'LOGIN','Student Alex Johnson logged in','127.0.0.1',DATE_SUB(NOW(),INTERVAL 30 MINUTE)),
(7,'SUBMIT','Submitted Assignment: ER Diagram Design','127.0.0.1',DATE_SUB(NOW(),INTERVAL 25 MINUTE)),
(9,'LOGIN','Student Avery Thomas logged in','127.0.0.1',DATE_SUB(NOW(),INTERVAL 20 MINUTE));

SELECT 'Scholario 2.0 — DB ready!' AS status;

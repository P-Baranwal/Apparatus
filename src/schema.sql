-- =====================================================================
-- schema.sql  --  WCA database (Team 41, Phase 3 Stage D schema)
-- MySQL 8.0.16+ (CHECK constraints are enforced from 8.0.16).
-- Run with:  mysql -u <user> -p < schema.sql
-- 27 tables, FK-ordered. Re-runnable: drops and recreates the database.
-- =====================================================================

DROP DATABASE IF EXISTS wca_db;
CREATE DATABASE wca_db CHARACTER SET utf8mb4;
USE wca_db;

-- ---------------------------------------------------------------------
-- Reference tables
-- ---------------------------------------------------------------------

CREATE TABLE continents (
  Continent_ID  VARCHAR(20)  NOT NULL,
  Name          VARCHAR(50)  NOT NULL,
  Record_Code   VARCHAR(5)   NOT NULL,          -- AfR, AsR, ER, NAR, OcR, SAR
  PRIMARY KEY (Continent_ID),
  UNIQUE KEY uq_continents_name (Name)
);

CREATE TABLE countries (
  Country_ID    VARCHAR(60)  NOT NULL,          -- WCA string id: 'India', 'USA', 'Hong Kong'
  ISO2          CHAR(2)      NOT NULL,
  Name          VARCHAR(100) NOT NULL,
  Continent_ID  VARCHAR(20)  NOT NULL,
  PRIMARY KEY (Country_ID),
  UNIQUE KEY uq_countries_iso2 (ISO2),
  CONSTRAINT fk_countries_continent FOREIGN KEY (Continent_ID)
    REFERENCES continents (Continent_ID) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE regions (
  Region_ID         INT          NOT NULL,
  Region_Name       VARCHAR(100) NOT NULL,
  Parent_Region_ID  INT          NULL,
  PRIMARY KEY (Region_ID),
  CONSTRAINT fk_regions_parent FOREIGN KEY (Parent_Region_ID)
    REFERENCES regions (Region_ID) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE teams (
  Team_ID        VARCHAR(30)  NOT NULL,
  Team_Name      VARCHAR(150) NOT NULL,
  Kind           VARCHAR(20)  NOT NULL,         -- board / committee / team
  Contact_Email  VARCHAR(255) NOT NULL,
  PRIMARY KEY (Team_ID)
);

CREATE TABLE events (
  Event_ID      VARCHAR(10)  NOT NULL,
  Event_Name    VARCHAR(100) NOT NULL,
  Display_Rank  INT          NOT NULL,
  Result_Kind   VARCHAR(20)  NOT NULL,          -- time / number / multi
  Status        VARCHAR(10)  NOT NULL,
  PRIMARY KEY (Event_ID),
  UNIQUE KEY uq_events_name (Event_Name),
  CONSTRAINT chk_events_status CHECK (Status IN ('official', 'retired'))
);

CREATE TABLE formats (
  Format_ID          VARCHAR(5)  NOT NULL,
  Format_Name        VARCHAR(50) NOT NULL,
  Expected_Attempts  TINYINT     NOT NULL,
  Sort_By            VARCHAR(10) NOT NULL,      -- single / average
  Trimmed_Per_Side   TINYINT     NOT NULL DEFAULT 0,
  PRIMARY KEY (Format_ID),
  UNIQUE KEY uq_formats_name (Format_Name),
  CONSTRAINT chk_formats_attempts CHECK (Expected_Attempts BETWEEN 1 AND 5)
);

-- Which formats an event may use. Usage_1/Usage_2 = fixed columns (A7).
CREATE TABLE allows (
  Event_ID   VARCHAR(10) NOT NULL,
  Format_ID  VARCHAR(5)  NOT NULL,
  Usage_1    VARCHAR(15) NOT NULL,
  Usage_2    VARCHAR(15) NULL,
  PRIMARY KEY (Event_ID, Format_ID),
  CONSTRAINT fk_allows_event  FOREIGN KEY (Event_ID)
    REFERENCES events (Event_ID)   ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_allows_format FOREIGN KEY (Format_ID)
    REFERENCES formats (Format_ID) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT chk_allows_usage1 CHECK (Usage_1 IN ('full_round', 'cutoff_phase')),
  CONSTRAINT chk_allows_usage2 CHECK (Usage_2 IS NULL OR Usage_2 IN ('full_round', 'cutoff_phase'))
);

CREATE TABLE staff_role (
  Role_Code       VARCHAR(30)  NOT NULL,
  Description     VARCHAR(100) NOT NULL,
  Regulation_Ref  VARCHAR(10)  NOT NULL,
  PRIMARY KEY (Role_Code)
);

-- ---------------------------------------------------------------------
-- People
-- ---------------------------------------------------------------------

CREATE TABLE persons (
  Person_No       INT          NOT NULL AUTO_INCREMENT,
  WCA_ID          CHAR(10)     NULL,
  Romanized_Name  VARCHAR(255) NOT NULL,
  Local_Name      VARCHAR(255) NULL,
  Gender          CHAR(1)      NULL,
  Date_of_Birth   DATE         NOT NULL,        -- never exposed by the API
  Email           VARCHAR(255) NOT NULL,        -- never exposed by the API
  Country_ID      VARCHAR(60)  NOT NULL,
  Since_Date      DATE         NULL,            -- start of current representation (12-month rule)
  PRIMARY KEY (Person_No),
  UNIQUE KEY uq_persons_wca_id (WCA_ID),        -- NULLs allowed, non-NULLs unique (U1)
  KEY idx_persons_name (Romanized_Name),
  KEY idx_persons_country (Country_ID),
  CONSTRAINT fk_persons_country FOREIGN KEY (Country_ID)
    REFERENCES countries (Country_ID) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT chk_persons_wca_id
    CHECK (WCA_ID IS NULL OR REGEXP_LIKE(WCA_ID, '^[0-9]{4}[A-Z]{4}[0-9]{2}$', 'c')),
  CONSTRAINT chk_persons_gender CHECK (Gender IS NULL OR Gender IN ('m', 'f', 'o'))
);

CREATE TABLE previous_identities (
  Person_No        INT          NOT NULL,
  Old_Name         VARCHAR(255) NOT NULL,
  Old_Country_ID   VARCHAR(60)  NOT NULL,
  Valid_Until      DATE         NOT NULL,
  PRIMARY KEY (Person_No, Old_Name, Old_Country_ID, Valid_Until),
  CONSTRAINT fk_previd_person  FOREIGN KEY (Person_No)
    REFERENCES persons (Person_No)     ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_previd_country FOREIGN KEY (Old_Country_ID)
    REFERENCES countries (Country_ID)  ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Subclass of PERSON: a row exists exactly when persons.WCA_ID IS NOT NULL.
CREATE TABLE competitors (
  Person_No  INT NOT NULL,
  PRIMARY KEY (Person_No),
  CONSTRAINT fk_competitors_person FOREIGN KEY (Person_No)
    REFERENCES persons (Person_No) ON UPDATE CASCADE ON DELETE CASCADE
);

-- Subclass of PERSON. Location was removed at Stage D (3NF); use regions.Region_Name.
CREATE TABLE delegate (
  Person_No             INT          NOT NULL,
  Delegate_Status       ENUM('trainee', 'junior', 'full', 'regional', 'senior') NOT NULL,
  WCA_Email             VARCHAR(255) NULL,      -- 128 trainees have no published e-mail
  Appointed_On          DATE         NOT NULL,
  Supervisor_Person_No  INT          NULL,      -- recursive SUPERVISES
  Region_ID             INT          NOT NULL,
  PRIMARY KEY (Person_No),
  UNIQUE KEY uq_delegate_email (WCA_Email),
  KEY idx_delegate_supervisor (Supervisor_Person_No),
  CONSTRAINT fk_delegate_person FOREIGN KEY (Person_No)
    REFERENCES persons (Person_No)  ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_delegate_supervisor FOREIGN KEY (Supervisor_Person_No)
    REFERENCES delegate (Person_No) ON UPDATE RESTRICT ON DELETE RESTRICT,
  CONSTRAINT fk_delegate_region FOREIGN KEY (Region_ID)
    REFERENCES regions (Region_ID)  ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE member_of (
  Person_No   INT         NOT NULL,
  Team_ID     VARCHAR(30) NOT NULL,
  Role        VARCHAR(30) NOT NULL,             -- leader / member / ...
  Start_Date  DATE        NOT NULL,
  End_Date    DATE        NULL,
  PRIMARY KEY (Person_No, Team_ID),
  CONSTRAINT fk_member_person FOREIGN KEY (Person_No)
    REFERENCES persons (Person_No) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_member_team   FOREIGN KEY (Team_ID)
    REFERENCES teams (Team_ID)     ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT chk_member_dates CHECK (End_Date IS NULL OR End_Date >= Start_Date)
);

-- ---------------------------------------------------------------------
-- Competitions
-- ---------------------------------------------------------------------

CREATE TABLE competitions (
  Competition_ID        VARCHAR(50)   NOT NULL,
  Name                  VARCHAR(255)  NOT NULL,
  Short_Name            VARCHAR(255)  NOT NULL,
  Venue_Name            VARCHAR(255)  NOT NULL,
  Street_Address        TEXT          NULL,
  Venue_Details         TEXT          NULL,
  City                  VARCHAR(255)  NOT NULL,
  Latitude              DECIMAL(9,6)  NULL,
  Longitude             DECIMAL(9,6)  NULL,
  Start_Date            DATE          NOT NULL,
  End_Date              DATE          NOT NULL,
  Opens_At              DATETIME      NULL,     -- registration window
  Closes_At             DATETIME      NULL,
  Amount                INT           NULL,     -- entry fee, minor units as published
  Currency_Code         CHAR(3)       NULL,
  Competitor_Limit      INT           NULL,
  Refund_Policy_Percent TINYINT       NULL,
  Website               VARCHAR(500)  NULL,
  Announced_At          DATETIME      NULL,
  Cancelled_At          DATETIME      NULL,
  Results_Posted_At     DATETIME      NULL,
  Country_ID            VARCHAR(60)   NOT NULL,
  Main_Event_ID         VARCHAR(10)   NULL,
  PRIMARY KEY (Competition_ID),
  KEY idx_competitions_start (Start_Date),
  KEY idx_competitions_country (Country_ID),
  KEY idx_competitions_main_event (Main_Event_ID),
  CONSTRAINT fk_competitions_country FOREIGN KEY (Country_ID)
    REFERENCES countries (Country_ID) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_competitions_main_event FOREIGN KEY (Main_Event_ID)
    REFERENCES events (Event_ID)      ON UPDATE CASCADE ON DELETE SET NULL,
  CONSTRAINT chk_comp_dates   CHECK (End_Date >= Start_Date),
  CONSTRAINT chk_comp_window  CHECK (Opens_At IS NULL OR Closes_At IS NULL OR Closes_At >= Opens_At),
  CONSTRAINT chk_comp_limit   CHECK (Competitor_Limit IS NULL OR Competitor_Limit > 0),
  CONSTRAINT chk_comp_refund  CHECK (Refund_Policy_Percent IS NULL OR Refund_Policy_Percent BETWEEN 0 AND 100),
  CONSTRAINT chk_comp_lat     CHECK (Latitude  IS NULL OR Latitude  BETWEEN -90  AND 90),
  CONSTRAINT chk_comp_lon     CHECK (Longitude IS NULL OR Longitude BETWEEN -180 AND 180)
);

CREATE TABLE championship_types (
  Competition_ID    VARCHAR(50) NOT NULL,
  Championship_Type VARCHAR(30) NOT NULL,       -- 'world', '_Asia', 'IN', ...
  PRIMARY KEY (Competition_ID, Championship_Type),
  CONSTRAINT fk_champ_competition FOREIGN KEY (Competition_ID)
    REFERENCES competitions (Competition_ID) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE competition_delegates (            -- DELEGATES relationship
  Person_No       INT         NOT NULL,
  Competition_ID  VARCHAR(50) NOT NULL,
  PRIMARY KEY (Person_No, Competition_ID),
  CONSTRAINT fk_compdel_delegate FOREIGN KEY (Person_No)
    REFERENCES delegate (Person_No)          ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_compdel_competition FOREIGN KEY (Competition_ID)
    REFERENCES competitions (Competition_ID) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE competition_organizers (           -- ORGANIZES relationship
  Person_No       INT         NOT NULL,
  Competition_ID  VARCHAR(50) NOT NULL,
  PRIMARY KEY (Person_No, Competition_ID),
  CONSTRAINT fk_comporg_person FOREIGN KEY (Person_No)
    REFERENCES persons (Person_No)           ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_comporg_competition FOREIGN KEY (Competition_ID)
    REFERENCES competitions (Competition_ID) ON UPDATE CASCADE ON DELETE CASCADE
);

-- Weak entity: owned by competition + event.
CREATE TABLE rounds (
  Competition_ID    VARCHAR(50) NOT NULL,
  Event_ID          VARCHAR(10) NOT NULL,
  Round_Number      TINYINT     NOT NULL,
  Format_ID         VARCHAR(5)  NOT NULL,
  Per_Attempt       INT         NULL,             -- time limit (A5); NULL for 333fm / 333mbf
  Cutoff_Attempts   TINYINT     NULL,
  Cutoff_Value      INT         NULL,
  Adv_Type          VARCHAR(20) NULL,             -- ranking / percent / attainment; NULL for finals
  Adv_Level         INT         NULL,
  Is_Dual           BOOLEAN     NOT NULL DEFAULT 0,
  Is_Head_to_Head   BOOLEAN     NOT NULL DEFAULT 0,
  Last_Day          DATE        NOT NULL,
  PRIMARY KEY (Competition_ID, Event_ID, Round_Number),
  KEY idx_rounds_event (Event_ID),
  KEY idx_rounds_format (Format_ID),
  CONSTRAINT fk_rounds_competition FOREIGN KEY (Competition_ID)
    REFERENCES competitions (Competition_ID) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_rounds_event  FOREIGN KEY (Event_ID)
    REFERENCES events (Event_ID)   ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_rounds_format FOREIGN KEY (Format_ID)
    REFERENCES formats (Format_ID) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT chk_rounds_number CHECK (Round_Number BETWEEN 1 AND 4),
  CONSTRAINT chk_rounds_cutoff CHECK ((Cutoff_Attempts IS NULL) = (Cutoff_Value IS NULL)),
  CONSTRAINT chk_rounds_adv    CHECK ((Adv_Type IS NULL) = (Adv_Level IS NULL))
);

-- Cumulative time limit shared across rounds of the same competition (A8).
CREATE TABLE cumulative_scope (
  Competition_ID       VARCHAR(50) NOT NULL,
  Event_ID             VARCHAR(10) NOT NULL,
  Round_Number         TINYINT     NOT NULL,
  Scope_Event_ID       VARCHAR(10) NOT NULL,
  Scope_Round_Number   TINYINT     NOT NULL,
  PRIMARY KEY (Competition_ID, Event_ID, Round_Number, Scope_Event_ID, Scope_Round_Number),
  CONSTRAINT fk_cumscope_round FOREIGN KEY (Competition_ID, Event_ID, Round_Number)
    REFERENCES rounds (Competition_ID, Event_ID, Round_Number) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_cumscope_scope FOREIGN KEY (Competition_ID, Scope_Event_ID, Scope_Round_Number)
    REFERENCES rounds (Competition_ID, Event_ID, Round_Number) ON UPDATE CASCADE ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- Registrations
-- ---------------------------------------------------------------------

CREATE TABLE registrations (
  Competition_ID    VARCHAR(50) NOT NULL,
  Registrant_No     INT         NOT NULL,         -- restarts at 1 in each competition
  Person_No         INT         NOT NULL,
  Status            ENUM('accepted', 'waiting_list', 'pending', 'cancelled', 'rejected') NOT NULL,
  Registered_At     DATETIME    NOT NULL,
  Guests            TINYINT     NOT NULL DEFAULT 0,
  Guardian_Consent  BOOLEAN     NOT NULL DEFAULT 0,
  PRIMARY KEY (Competition_ID, Registrant_No),
  UNIQUE KEY uq_reg_person (Competition_ID, Person_No),
  KEY idx_reg_person (Person_No),
  CONSTRAINT fk_reg_competition FOREIGN KEY (Competition_ID)
    REFERENCES competitions (Competition_ID) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_reg_person FOREIGN KEY (Person_No)
    REFERENCES persons (Person_No)           ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT chk_reg_registrant CHECK (Registrant_No >= 1),
  CONSTRAINT chk_reg_guests     CHECK (Guests BETWEEN 0 AND 10)
);

CREATE TABLE selects (                           -- events chosen in a registration
  Competition_ID  VARCHAR(50) NOT NULL,
  Registrant_No   INT         NOT NULL,
  Event_ID        VARCHAR(10) NOT NULL,
  PRIMARY KEY (Competition_ID, Registrant_No, Event_ID),
  KEY idx_selects_event (Event_ID),
  CONSTRAINT fk_selects_registration FOREIGN KEY (Competition_ID, Registrant_No)
    REFERENCES registrations (Competition_ID, Registrant_No) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_selects_event FOREIGN KEY (Event_ID)
    REFERENCES events (Event_ID) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ---------------------------------------------------------------------
-- Results
-- Values: centiseconds, move counts or multi-blind encoding; -1 = DNF, -2 = DNS.
-- Best/Average/Position/*_Record are stored (controlled redundancy, section 1.7).
-- ---------------------------------------------------------------------

CREATE TABLE results (
  Result_ID       BIGINT      NOT NULL,           -- real WCA result id
  Competition_ID  VARCHAR(50) NOT NULL,
  Event_ID        VARCHAR(10) NOT NULL,
  Round_Number    TINYINT     NOT NULL,
  Person_No       INT         NOT NULL,
  Country_ID      VARCHAR(60) NOT NULL,           -- country represented on the day (U11)
  Best            BIGINT      NOT NULL,
  Average         BIGINT      NOT NULL,
  Position        INT         NULL,
  Single_Record   VARCHAR(3)  NULL,
  Average_Record  VARCHAR(3)  NULL,
  PRIMARY KEY (Result_ID),
  UNIQUE KEY uq_results_round_person (Competition_ID, Event_ID, Round_Number, Person_No),
  KEY idx_results_person (Person_No),
  KEY idx_results_country (Country_ID),
  KEY idx_results_event_best (Event_ID, Best),
  KEY idx_results_event_avg (Event_ID, Average),
  CONSTRAINT fk_results_round FOREIGN KEY (Competition_ID, Event_ID, Round_Number)
    REFERENCES rounds (Competition_ID, Event_ID, Round_Number) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_results_person FOREIGN KEY (Person_No)
    REFERENCES persons (Person_No)    ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_results_country FOREIGN KEY (Country_ID)
    REFERENCES countries (Country_ID) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT chk_results_best     CHECK (Best    >= -2),
  CONSTRAINT chk_results_average  CHECK (Average >= -2),
  CONSTRAINT chk_results_position CHECK (Position IS NULL OR Position >= 1),
  CONSTRAINT chk_results_srec CHECK (Single_Record  IS NULL OR Single_Record  IN ('WR','AfR','AsR','ER','NAR','OcR','SAR','NR')),
  CONSTRAINT chk_results_arec CHECK (Average_Record IS NULL OR Average_Record IN ('WR','AfR','AsR','ER','NAR','OcR','SAR','NR'))
);

CREATE TABLE attempts (
  Result_ID   BIGINT   NOT NULL,
  Attempt_No  TINYINT  NOT NULL,
  Value       BIGINT   NOT NULL,
  PRIMARY KEY (Result_ID, Attempt_No),
  CONSTRAINT fk_attempts_result FOREIGN KEY (Result_ID)
    REFERENCES results (Result_ID) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT chk_attempts_no    CHECK (Attempt_No BETWEEN 1 AND 5),
  CONSTRAINT chk_attempts_value CHECK (Value >= -2)
);

-- ---------------------------------------------------------------------
-- Scrambles and staff
-- ---------------------------------------------------------------------

CREATE TABLE scrambles (
  Competition_ID  VARCHAR(50) NOT NULL,
  Event_ID        VARCHAR(10) NOT NULL,
  Round_Number    TINYINT     NOT NULL,
  Group_ID        VARCHAR(5)  NOT NULL,           -- A, B, ..., AA
  Is_Extra        BOOLEAN     NOT NULL,
  Scramble_No     SMALLINT    NOT NULL,
  PRIMARY KEY (Competition_ID, Event_ID, Round_Number, Group_ID, Is_Extra, Scramble_No),
  CONSTRAINT fk_scrambles_round FOREIGN KEY (Competition_ID, Event_ID, Round_Number)
    REFERENCES rounds (Competition_ID, Event_ID, Round_Number) ON UPDATE CASCADE ON DELETE CASCADE
);

-- DESIGN CHANGE: Seq_Index added so each sequence has a short key
-- (a scramble can have several sequences, and Sequence is too long to be part of a key).
CREATE TABLE scramble_sequences (
  Competition_ID  VARCHAR(50) NOT NULL,
  Event_ID        VARCHAR(10) NOT NULL,
  Round_Number    TINYINT     NOT NULL,
  Group_ID        VARCHAR(5)  NOT NULL,
  Is_Extra        BOOLEAN     NOT NULL,
  Scramble_No     SMALLINT    NOT NULL,
  Seq_Index       TINYINT     NOT NULL DEFAULT 1,
  Sequence        TEXT        NOT NULL,
  PRIMARY KEY (Competition_ID, Event_ID, Round_Number, Group_ID, Is_Extra, Scramble_No, Seq_Index),
  CONSTRAINT fk_scrseq_scramble FOREIGN KEY
    (Competition_ID, Event_ID, Round_Number, Group_ID, Is_Extra, Scramble_No)
    REFERENCES scrambles (Competition_ID, Event_ID, Round_Number, Group_ID, Is_Extra, Scramble_No)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE assigned_as (                       -- ternary: PERSON - ROUND - STAFF_ROLE
  Person_No       INT         NOT NULL,
  Competition_ID  VARCHAR(50) NOT NULL,
  Event_ID        VARCHAR(10) NOT NULL,
  Round_Number    TINYINT     NOT NULL,
  Role_Code       VARCHAR(30) NOT NULL,
  PRIMARY KEY (Person_No, Competition_ID, Event_ID, Round_Number, Role_Code),
  KEY idx_assigned_round (Competition_ID, Event_ID, Round_Number),
  KEY idx_assigned_role (Role_Code),
  CONSTRAINT fk_assigned_person FOREIGN KEY (Person_No)
    REFERENCES persons (Person_No)     ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_assigned_round FOREIGN KEY (Competition_ID, Event_ID, Round_Number)
    REFERENCES rounds (Competition_ID, Event_ID, Round_Number) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_assigned_role FOREIGN KEY (Role_Code)
    REFERENCES staff_role (Role_Code)  ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE assigned_as_slots (
  Person_No       INT         NOT NULL,
  Competition_ID  VARCHAR(50) NOT NULL,
  Event_ID        VARCHAR(10) NOT NULL,
  Round_Number    TINYINT     NOT NULL,
  Role_Code       VARCHAR(30) NOT NULL,
  Group_ID        VARCHAR(5)  NOT NULL,
  Station_No      INT         NULL,
  PRIMARY KEY (Person_No, Competition_ID, Event_ID, Round_Number, Role_Code, Group_ID),
  CONSTRAINT fk_slots_assignment FOREIGN KEY
    (Person_No, Competition_ID, Event_ID, Round_Number, Role_Code)
    REFERENCES assigned_as (Person_No, Competition_ID, Event_ID, Round_Number, Role_Code)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT chk_slots_station CHECK (Station_No IS NULL OR Station_No >= 1)
);

-- ---------------------------------------------------------------------
-- Rule enforced in the database: a registration cannot be deleted once the
-- person has results in that competition (feature F10).
-- (FK cascades from competitions/registrations do not fire triggers.)
-- ---------------------------------------------------------------------

DELIMITER //
CREATE TRIGGER trg_registrations_no_delete_with_results
BEFORE DELETE ON registrations
FOR EACH ROW
BEGIN
  IF EXISTS (SELECT 1 FROM results
              WHERE Competition_ID = OLD.Competition_ID
                AND Person_No      = OLD.Person_No) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Cannot delete this registration because the competitor already has results in this competition.';
  END IF;
END//
DELIMITER ;
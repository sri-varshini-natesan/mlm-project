-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Jun 15, 2026 at 07:13 AM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.0.30

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `mlm_database`
--

-- --------------------------------------------------------

--
-- Table structure for table `admin_audit_logs`
--

CREATE TABLE `admin_audit_logs` (
  `id` int(11) NOT NULL,
  `performed_by` varchar(50) NOT NULL,
  `action_type` enum('LOGIN','WALLET_EDIT','INCOME_EDIT','WITHDRAWAL_ACTION','USER_MANAGEMENT') NOT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `details` text NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `admin_holidays`
--

CREATE TABLE `admin_holidays` (
  `id` int(11) NOT NULL,
  `holiday_date` date NOT NULL,
  `holiday_name` varchar(100) NOT NULL,
  `holiday_type` enum('public','internal','emergency') DEFAULT 'public',
  `pause_roi` tinyint(1) DEFAULT 1,
  `created_by` varchar(50) DEFAULT 'ADMIN',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `audit_logs`
--

CREATE TABLE `audit_logs` (
  `id` int(11) NOT NULL,
  `log_type` varchar(50) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `action` varchar(255) DEFAULT NULL,
  `detail` text DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `courses`
--

CREATE TABLE `courses` (
  `id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `category` varchar(100) DEFAULT NULL,
  `price` decimal(10,2) DEFAULT NULL,
  `roi_percent` decimal(5,2) DEFAULT 0.00,
  `duration_days` int(11) DEFAULT 250,
  `total_cnt` int(11) DEFAULT 0,
  `visibility` enum('Public','App Only') DEFAULT 'Public',
  `status` enum('Active','Inactive') DEFAULT 'Active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `courses`
--

INSERT INTO `courses` (`id`, `name`, `category`, `price`, `roi_percent`, `duration_days`, `total_cnt`, `visibility`, `status`) VALUES
(1, 'Course BC1', 'Basic', 500.00, 1.00, 250, 0, 'Public', 'Active'),
(2, 'Course BC2', 'Basic', 1700.00, 1.00, 250, 0, 'Public', 'Active'),
(3, 'Course BC3', 'Basic', 4400.00, 1.00, 250, 0, 'Public', 'Active'),
(4, 'Course MC1', 'Master', 10400.00, 1.20, 250, 0, 'Public', 'Active'),
(5, 'Course MC2', 'Master', 24500.00, 1.20, 250, 0, 'Public', 'Active'),
(6, 'Course MC3', 'Master', 49000.00, 1.20, 250, 0, 'Public', 'Active'),
(7, 'Course AC1', 'Advanced', 99900.00, 1.50, 250, 0, 'Public', 'Active'),
(8, 'Course AC2', 'Advanced', 140000.00, 1.50, 250, 0, 'Public', 'Active'),
(9, 'Course AC3', 'Advanced', 199000.00, 1.50, 250, 0, 'Public', 'Active'),
(10, 'Course AC4', 'Advanced', 299000.00, 1.50, 250, 0, 'Public', 'Active');

-- --------------------------------------------------------

--
-- Table structure for table `deposits`
--

CREATE TABLE `deposits` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `payment_method` varchar(50) DEFAULT NULL,
  `txn_ref` varchar(100) DEFAULT NULL,
  `proof_image` varchar(255) DEFAULT NULL,
  `status` varchar(20) DEFAULT 'PENDING',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `approved_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `holidays`
--

CREATE TABLE `holidays` (
  `id` int(11) NOT NULL,
  `name` varchar(100) NOT NULL,
  `holiday_date` date NOT NULL,
  `description` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `kyc_verifications`
--

CREATE TABLE `kyc_verifications` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `document_type` varchar(50) DEFAULT NULL,
  `document_number` varchar(100) DEFAULT NULL,
  `document_image` varchar(255) DEFAULT NULL,
  `status` varchar(20) DEFAULT 'PENDING',
  `rejection_reason` text DEFAULT NULL,
  `submitted_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `reviewed_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `notifications`
--

CREATE TABLE `notifications` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `title` varchar(255) NOT NULL,
  `message` text NOT NULL,
  `type` varchar(50) DEFAULT 'push',
  `is_read` tinyint(1) DEFAULT 0,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `packages`
--

CREATE TABLE `packages` (
  `id` int(11) NOT NULL,
  `name` varchar(100) NOT NULL,
  `price` decimal(10,2) NOT NULL,
  `roi_percent` decimal(5,2) NOT NULL,
  `duration_days` int(11) DEFAULT 250,
  `status` varchar(20) DEFAULT 'active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `support_tickets`
--

CREATE TABLE `support_tickets` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `subject` varchar(200) NOT NULL,
  `priority` enum('LOW','MEDIUM','HIGH') DEFAULT 'MEDIUM',
  `status` enum('OPEN','PENDING','ESCALATED','CLOSED') DEFAULT 'OPEN',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `system_admins`
--

CREATE TABLE `system_admins` (
  `id` int(11) NOT NULL,
  `username` varchar(50) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` enum('SUPER','FINANCE','SUPPORT') DEFAULT 'SUPPORT',
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `system_logs`
--

CREATE TABLE `system_logs` (
  `id` int(11) NOT NULL,
  `log_type` varchar(50) DEFAULT NULL,
  `status` varchar(20) DEFAULT NULL,
  `message` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `system_logs`
--

INSERT INTO `system_logs` (`id`, `log_type`, `status`, `message`, `created_at`) VALUES
(1, 'daily_payout', 'SUCCESS', 'Daily incomes calculated successfully', '2026-06-13 05:28:14'),
(2, 'daily_payout', 'SUCCESS', 'Daily incomes calculated successfully', '2026-06-14 08:56:43');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `user_code` varchar(20) NOT NULL,
  `full_name` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `sponsor_id` int(11) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 0,
  `inactive_days` int(11) DEFAULT 0,
  `left_volume` decimal(15,2) DEFAULT 0.00,
  `right_volume` decimal(15,2) DEFAULT 0.00,
  `cashback_received` tinyint(1) DEFAULT 0,
  `captain_level` int(11) DEFAULT 0,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `dob` date DEFAULT NULL,
  `gender` varchar(10) DEFAULT NULL,
  `aadhar_no` varchar(20) DEFAULT NULL,
  `pan_no` varchar(20) DEFAULT NULL,
  `mobile` varchar(15) DEFAULT NULL,
  `password` varchar(255) DEFAULT NULL,
  `profile_img` varchar(255) DEFAULT NULL,
  `aadhar_file_path` varchar(255) DEFAULT NULL,
  `pan_file_path` varchar(255) DEFAULT NULL,
  `kyc_status` enum('PENDING','VERIFIED','REJECTED') DEFAULT 'PENDING',
  `admin_remarks` text DEFAULT NULL,
  `address` text DEFAULT NULL,
  `bank_acc_name` varchar(100) DEFAULT NULL,
  `bank_acc_no` varchar(50) DEFAULT NULL,
  `bank_ifsc` varchar(20) DEFAULT NULL,
  `upi_id` varchar(100) DEFAULT NULL,
  `upi_mobile` varchar(15) DEFAULT NULL,
  `leg` varchar(10) DEFAULT NULL,
  `placement_id` int(11) DEFAULT NULL,
  `wallet_balance` decimal(10,2) DEFAULT 0.00
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`id`, `user_code`, `full_name`, `email`, `sponsor_id`, `is_active`, `inactive_days`, `left_volume`, `right_volume`, `cashback_received`, `captain_level`, `created_at`, `dob`, `gender`, `aadhar_no`, `pan_no`, `mobile`, `password`, `profile_img`, `aadhar_file_path`, `pan_file_path`, `kyc_status`, `admin_remarks`, `address`, `bank_acc_name`, `bank_acc_no`, `bank_ifsc`, `upi_id`, `upi_mobile`, `leg`, `placement_id`, `wallet_balance`) VALUES
(1, 'MLM87872', 'John Doe', 'johndoe@mlm.com', NULL, 1, 0, 0.00, 0.00, 0, 0, '2026-05-31 06:53:30', NULL, NULL, '123456789012', 'ABCDE1234F', '9876543210', NULL, NULL, NULL, NULL, 'PENDING', NULL, '123 Main Street, Tech City', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0.00),
(7, 'MLM90710', 'user1234', 'user1234@gmail.com', 1, 1, 0, 0.00, 0.00, 0, 0, '2026-06-03 15:09:15', '2004-05-05', 'female', '122345678890', '1234567345', '9876543210', NULL, NULL, NULL, NULL, 'PENDING', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'right', 1, 0.00),
(10, 'JOHN', 'JOHN DOE', 'john@demo.com', NULL, 1, 0, 0.00, 0.00, 0, 0, '2026-06-04 16:46:19', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'PENDING', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0.00),
(12, 'MLM86899', 'Varshini', 'srivarshini9585833779@gmail.com', NULL, 1, 0, 0.00, 0.00, 0, 0, '2026-06-12 06:44:07', '2004-05-19', 'female', '987683200643', 'CUPN1234B1', '9585833779', 'varshini@2004', NULL, NULL, NULL, 'PENDING', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 245.00),
(17, 'MLM38272', 'test1', 'test1@gmail.com', 12, 1, 0, 0.00, 0.00, 0, 0, '2026-06-14 05:19:50', '2025-04-12', 'male', '122345676545', '1234564765', '9876543233', 'test1', NULL, NULL, NULL, 'PENDING', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'left', 12, 5.00),
(18, 'MLM36483', 'test2', 'test2@gmail.com', 12, 1, 0, 0.00, 0.00, 0, 0, '2026-06-14 05:22:27', '2025-08-14', 'male', '345217689236', '6574839201', '9988776655', 'test2', NULL, NULL, NULL, 'PENDING', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'right', 12, 5.00),
(19, 'MLM63356', 'test3', 'test3@gmail.com', 12, 1, 0, 0.00, 0.00, 0, 0, '2026-06-14 13:15:05', '2003-07-07', 'male', '143567832911', '4294832958', '2428473759', 'test3', NULL, NULL, NULL, 'PENDING', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'right', 18, 4500.00);

-- --------------------------------------------------------

--
-- Table structure for table `user_courses`
--

CREATE TABLE `user_courses` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `course_id` int(11) DEFAULT NULL,
  `status` enum('ACTIVE','EXPIRED') DEFAULT 'ACTIVE',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `expires_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `user_courses`
--

INSERT INTO `user_courses` (`id`, `user_id`, `course_id`, `status`, `created_at`, `expires_at`) VALUES
(1, 1, NULL, 'ACTIVE', '2026-06-12 13:40:32', NULL),
(2, 7, NULL, 'ACTIVE', '2026-06-12 13:40:32', NULL),
(3, 1, NULL, 'ACTIVE', '2026-06-12 13:40:32', NULL),
(7, 12, NULL, 'ACTIVE', '2026-06-12 15:01:44', NULL),
(8, 17, 1, 'ACTIVE', '2026-06-14 08:33:55', '2027-02-19 14:03:55'),
(9, 18, 1, 'ACTIVE', '2026-06-14 08:33:55', '2027-02-19 14:03:55'),
(10, 19, 1, 'ACTIVE', '2026-06-14 13:32:03', '2027-02-19 19:02:03');

-- --------------------------------------------------------

--
-- Table structure for table `wallet_transactions`
--

CREATE TABLE `wallet_transactions` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `amount` decimal(15,2) NOT NULL,
  `transaction_type` enum('CREDIT','DEBIT') NOT NULL,
  `bonus_type` varchar(50) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `wallet_transactions`
--

INSERT INTO `wallet_transactions` (`id`, `user_id`, `amount`, `transaction_type`, `bonus_type`, `description`, `created_at`) VALUES
(2, 1, 45680.00, 'CREDIT', '', 'Executive Demo Data', '2026-05-31 13:20:16'),
(3, 1, 12350.00, 'CREDIT', 'DIRECT_SPONSOR', 'Executive Demo Data', '2026-05-31 13:20:16'),
(4, 1, 18600.00, 'CREDIT', 'BINARY_MATCH', 'Executive Demo Data', '2026-05-31 13:20:16'),
(5, 1, 5470.00, 'CREDIT', 'SELF_REPURCHASE', 'Executive Demo Data', '2026-05-31 13:20:16'),
(6, 1, 43200.00, 'CREDIT', 'CAPTAIN_ROYALTY', 'Executive Demo Data', '2026-05-31 13:20:16'),
(7, 1, 150.00, 'CREDIT', 'CASHBACK', 'Executive Demo Data', '2026-05-31 13:20:16'),
(8, 1, 68750.00, 'DEBIT', 'WITHDRAWAL', 'Executive Demo Data', '2026-05-31 13:20:16'),
(9, 12, 245.00, 'CREDIT', 'STAKING_BONUS', 'Daily ROI for Course MC2', '2026-06-13 05:28:14'),
(10, 17, 5.00, 'CREDIT', 'STAKING_BONUS', 'Daily ROI for Course BC1', '2026-06-14 08:56:43'),
(11, 18, 5.00, 'CREDIT', 'STAKING_BONUS', 'Daily ROI for Course BC1', '2026-06-14 08:56:43'),
(12, 12, 50.00, 'CREDIT', 'BINARY_MATCH', 'Matched 500.0 BV', '2026-06-14 08:56:43'),
(13, 19, 500.00, 'DEBIT', 'COURSE_PURCHASE', 'Purchased Course BC1', '2026-06-14 13:32:03'),
(14, 12, 50.00, 'CREDIT', 'DIRECT_SPONSOR', 'Direct Referral Bonus for Course BC1', '2026-06-14 13:32:03');

-- --------------------------------------------------------

--
-- Table structure for table `withdrawals`
--

CREATE TABLE `withdrawals` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `request_amount` decimal(15,2) NOT NULL,
  `tds_deduction` decimal(15,2) NOT NULL,
  `net_payable` decimal(15,2) NOT NULL,
  `status` enum('PENDING','APPROVED','REJECTED') DEFAULT 'PENDING',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `processed_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `withdrawals`
--

INSERT INTO `withdrawals` (`id`, `user_id`, `request_amount`, `tds_deduction`, `net_payable`, `status`, `created_at`, `processed_at`) VALUES
(1, 12, 100.00, 0.00, 100.00, 'PENDING', '2026-06-14 16:18:59', NULL);

--
-- Indexes for dumped tables
--

--
-- Indexes for table `admin_audit_logs`
--
ALTER TABLE `admin_audit_logs`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `admin_holidays`
--
ALTER TABLE `admin_holidays`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `holiday_date` (`holiday_date`);

--
-- Indexes for table `audit_logs`
--
ALTER TABLE `audit_logs`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `courses`
--
ALTER TABLE `courses`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `deposits`
--
ALTER TABLE `deposits`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `holidays`
--
ALTER TABLE `holidays`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `kyc_verifications`
--
ALTER TABLE `kyc_verifications`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `notifications`
--
ALTER TABLE `notifications`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `packages`
--
ALTER TABLE `packages`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `support_tickets`
--
ALTER TABLE `support_tickets`
  ADD PRIMARY KEY (`id`),
  ADD KEY `user_id` (`user_id`);

--
-- Indexes for table `system_admins`
--
ALTER TABLE `system_admins`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`),
  ADD UNIQUE KEY `email` (`email`);

--
-- Indexes for table `system_logs`
--
ALTER TABLE `system_logs`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `user_code` (`user_code`),
  ADD UNIQUE KEY `email` (`email`),
  ADD UNIQUE KEY `aadhar_no` (`aadhar_no`),
  ADD UNIQUE KEY `pan_no` (`pan_no`),
  ADD KEY `idx_users_sponsor_active` (`sponsor_id`,`is_active`);

--
-- Indexes for table `user_courses`
--
ALTER TABLE `user_courses`
  ADD PRIMARY KEY (`id`),
  ADD KEY `user_id` (`user_id`),
  ADD KEY `idx_user_courses_status` (`status`);

--
-- Indexes for table `wallet_transactions`
--
ALTER TABLE `wallet_transactions`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_transactions_user_type` (`user_id`,`transaction_type`);

--
-- Indexes for table `withdrawals`
--
ALTER TABLE `withdrawals`
  ADD PRIMARY KEY (`id`),
  ADD KEY `user_id` (`user_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `admin_audit_logs`
--
ALTER TABLE `admin_audit_logs`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `admin_holidays`
--
ALTER TABLE `admin_holidays`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `audit_logs`
--
ALTER TABLE `audit_logs`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `courses`
--
ALTER TABLE `courses`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=11;

--
-- AUTO_INCREMENT for table `deposits`
--
ALTER TABLE `deposits`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `holidays`
--
ALTER TABLE `holidays`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `kyc_verifications`
--
ALTER TABLE `kyc_verifications`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `notifications`
--
ALTER TABLE `notifications`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `packages`
--
ALTER TABLE `packages`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `support_tickets`
--
ALTER TABLE `support_tickets`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `system_admins`
--
ALTER TABLE `system_admins`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `system_logs`
--
ALTER TABLE `system_logs`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=20;

--
-- AUTO_INCREMENT for table `user_courses`
--
ALTER TABLE `user_courses`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=11;

--
-- AUTO_INCREMENT for table `wallet_transactions`
--
ALTER TABLE `wallet_transactions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=15;

--
-- AUTO_INCREMENT for table `withdrawals`
--
ALTER TABLE `withdrawals`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `support_tickets`
--
ALTER TABLE `support_tickets`
  ADD CONSTRAINT `support_tickets_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `users`
--
ALTER TABLE `users`
  ADD CONSTRAINT `users_ibfk_1` FOREIGN KEY (`sponsor_id`) REFERENCES `users` (`id`) ON DELETE SET NULL;

--
-- Constraints for table `user_courses`
--
ALTER TABLE `user_courses`
  ADD CONSTRAINT `user_courses_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `wallet_transactions`
--
ALTER TABLE `wallet_transactions`
  ADD CONSTRAINT `wallet_transactions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `withdrawals`
--
ALTER TABLE `withdrawals`
  ADD CONSTRAINT `withdrawals_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;

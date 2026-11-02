-- phpMyAdmin SQL Dump
-- version 2.11.6
-- http://www.phpmyadmin.net
--
-- Host: localhost
-- Generation Time: Jul 17, 2026 at 05:16 AM
-- Server version: 5.0.51
-- PHP Version: 5.2.6

SET SQL_MODE="NO_AUTO_VALUE_ON_ZERO";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;

--
-- Database: `1foodfreshnessdb`
--

-- --------------------------------------------------------

--
-- Table structure for table `foodinfodb`
--

CREATE TABLE `foodinfodb` (
  `id` bigint(50) NOT NULL auto_increment,
  `Name` varchar(250) NOT NULL,
  `Type` varchar(250) NOT NULL,
  `Info` varchar(1000) NOT NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB  DEFAULT CHARSET=latin1 AUTO_INCREMENT=5 ;

--
-- Dumping data for table `foodinfodb`
--

INSERT INTO `foodinfodb` (`id`, `Name`, `Type`, `Info`) VALUES
(2, 'FreshApple', 'Fresh', 'sasasasas'),
(3, 'FreshBanana', 'Fresh', 'safdssczxxz'),
(4, 'RottenApple', 'Rotten', 'eeeesxxasas');

-- --------------------------------------------------------

--
-- Table structure for table `regtb`
--

CREATE TABLE `regtb` (
  `uid` bigint(250) NOT NULL auto_increment,
  `name` varchar(250) NOT NULL,
  `gender` varchar(10) NOT NULL,
  `age` varchar(10) NOT NULL,
  `email` varchar(250) NOT NULL,
  `mobile` varchar(250) NOT NULL,
  `address` varchar(250) NOT NULL,
  `UserName` varchar(250) NOT NULL,
  `Password` varchar(250) NOT NULL,
  PRIMARY KEY  (`uid`)
) ENGINE=InnoDB  DEFAULT CHARSET=latin1 AUTO_INCREMENT=2 ;

--
-- Dumping data for table `regtb`
--

INSERT INTO `regtb` (`uid`, `name`, `gender`, `age`, `email`, `mobile`, `address`, `UserName`, `Password`) VALUES
(1, 'mark', 'male', '25', 'fantasypythonprojects@gmail.com', '8148526949', 'Trichy', 'mark', 'mark');

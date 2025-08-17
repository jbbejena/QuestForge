# WWII Text Adventure Game

## Overview

This is a mobile-optimized, text-based WWII adventure game built with Flask. Players create soldiers with customizable attributes (name, rank, class, weapon) and embark on various missions with different difficulty levels. The game features an achievement system that unlocks historical WWII trivia facts as players progress, combining entertainment with educational content. The application is designed as a Progressive Web App (PWA) with mobile-first responsive design and optional AI-powered storytelling through OpenAI integration.

## Recent Changes (August 2025)

- **Modular Architecture Refactor** - Split monolithic 1500+ line app.py into focused modules: game_logic.py, mission_generator.py, error_handlers.py, and performance_utils.py
- **Database Type Safety** - Fixed 30+ SQLite/PostgreSQL type errors with proper row access patterns for both database systems
- **Enhanced Error Handling** - Centralized error recovery, session validation, and graceful degradation patterns
- **Performance Optimizations** - Added session caching, story compression, rate limiting, and performance monitoring
- **Improved Data Management** - Better use of Replit's database capabilities with type-safe operations and connection management
- **Combat System Fix (August 17, 2025)** - Restored missing combat detection logic that was lost during modular refactor
- **Code Quality Improvements** - Fixed all LSP diagnostics errors, variable naming issues, and null-safety problems
- **Server Stability** - Resolved startup issues and exception handling problems for reliable deployment
- **Enhanced Auto-scroll System** - Significantly improved story text auto-scrolling during typewriter effect with smooth 50ms intervals
- **Complete Combat System** - Turn-based combat triggered by AI story keywords featuring tactical actions, health/resource management, and consequences
- **Advanced Keyboard Controls** - Comprehensive shortcuts including Ctrl+S (save), Ctrl+M (medkit), number keys for choices, and combat hotkeys
- **Backend API Integration** - Flask routes for combat mechanics, item usage, and save/load functionality with proper error handling
- **Mobile Combat Interface** - Responsive combat modal with animations and touch-friendly controls

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: Server-side rendered Jinja2 templates with vanilla JavaScript enhancements
- **Mobile-First Design**: Progressive Web App (PWA) with responsive CSS, touch handlers, and app manifest
- **UI Pattern**: Component-based design using CSS custom properties and modular HTML templates
- **JavaScript Features**: Touch optimization, typewriter effects, auto-save functionality, and loading states
- **Styling**: Military-themed color palette with CSS Grid and Flexbox for responsive layouts
- **Progressive Enhancement**: Core functionality works without JavaScript, enhanced experience with JS enabled

### Backend Architecture
- **Framework**: Flask web application with session-based state management and modular architecture
- **Architecture Pattern**: Modularized MVC structure with separated concerns across focused modules
  - **game_logic.py**: Core gameplay functions, combat resolution, mission outcomes
  - **mission_generator.py**: Dynamic mission creation and campaign progression
  - **error_handlers.py**: Centralized error handling and session management
  - **performance_utils.py**: Caching, compression, and performance monitoring
  - **database.py**: Type-safe database operations supporting both SQLite and PostgreSQL
  - **achievements.py**: Player progression and trivia unlock system
- **Game Logic**: Turn-based gameplay with enhanced combat mechanics, mission selection, and achievement tracking
- **AI Integration**: Optional OpenAI API integration for dynamic story generation with intelligent caching and graceful fallback
- **Session Management**: Enhanced Flask sessions with size optimization, validation, and cleanup mechanisms

### Data Storage Solutions
- **Session Storage**: Flask sessions store player data, game state, and progress (no persistent database)
- **Static Data**: Game content stored in Python dictionaries (missions, ranks, classes, weapons, trivia)
- **Achievement System**: In-memory tracking of player accomplishments with historical trivia unlocks
- **No Database Persistence**: Stateless design with session-only data retention

### Authentication and Authorization
- **Session-Based**: Simple Flask session management without user accounts or authentication
- **Single Player**: No multi-user support or persistent user profiles
- **State Management**: Game state maintained through browser sessions with configurable session lifetime

## External Dependencies

### Core Framework Dependencies
- **Flask 3.0.2**: Web framework providing routing, templating, session management, and WSGI application structure
- **python-dotenv 1.0.1**: Environment variable management for secure configuration handling
- **OpenAI 1.35.14**: Optional AI service integration for dynamic story generation and enhanced gameplay

### Frontend Libraries
- **Font Awesome 6.0.0**: Comprehensive icon library for military-themed UI elements and game symbols
- **No JavaScript Frameworks**: Vanilla JavaScript approach for optimal mobile performance and reduced bundle size

### Development and Deployment
- **Replit Platform**: Primary hosting environment with Nix-based package management and integrated development tools
- **PWA Standards**: Web App Manifest and Service Worker for offline capabilities and mobile app-like experience
- **Environment Configuration**: Flexible deployment supporting various hosting platforms through environment variables
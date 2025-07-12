# CS2 Enhanced Configuration - Your Example Format
metadata:
  game_name: "Counter-Strike 2"
  path: "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Counter-Strike Global Offensive\\game\\bin\\win64\\cs2.exe"
  version: "2.0"
  benchmark_duration: 110
  startup_wait: 30
  resolution: "1920x1080"
  preset: "High"

# Enhanced step-by-step workflow exactly as you requested
steps:
  1:
    description: "Right-click on Exit button to test context menu"
    find:
      type: "icon"
      text: "Exit"
      text_match: "contains"
    action: 
      type: "click"
      click_type: "right"  # Right-click as requested
    verify_success:
      - type: "icon"
        text: "Confirm"
        text_match: "contains"
    expected_delay: 5
    timeout: 20

  2:
    description: "Press Enter key on Play button area"
    find:
      type: "icon"
      text: "Play"
      text_match: "contains"
    action: 
      type: "keypress"
      key: "Return"  # Enter key as requested
    verify_success:
      - type: "icon"
        text: "Settings"
        text_match: "contains"
    expected_delay: 5
    timeout: 20

  3:
    description: "Press 'M' key while Settings is visible (hotkey navigation)"
    find:
      type: "icon"
      text: "Settings"
      text_match: "contains"
    action: 
      type: "keypress"
      key: "m"  # Single character key as requested
    verify_success:
      - type: "icon"
        text: "Video"
        text_match: "contains"
    expected_delay: 5
    timeout: 20

  4:
    description: "Click PLAY button to start game navigation"
    find:
      type: "icon"
      text: "PLAY"
      text_match: "contains"
    action: 
      type: "click"
      click_type: "left"  # Explicit left-click
    verify_success:
      - type: "icon"
        text: "MATCHMAKING"
        text_match: "contains"
      - type: "icon"
        text: "WORKSHOP MAPS"
        text_match: "contains"
    expected_delay: 2
    timeout: 20
    
  5:
    description: "Click WORKSHOP MAPS to open workshop browser"
    find:
      type: "icon"
      text: "WORKSHOP MAPS"
      text_match: "contains"
    action: 
      type: "click"
      click_type: "left"
    verify_success:
      - type: "icon"
        text: "Filter Maps"
        text_match: "contains"
    expected_delay: 5
    timeout: 20
    
  6:
    description: "Click CS2 FPS Bench map"
    find:
      type: "icon"
      text: "CS2 FPS Bench"
      text_match: "contains"
    action: 
      type: "click"
      click_type: "left"
    verify_success:
      - type: "icon"
        text: "GO"
        text_match: "exact"
    expected_delay: 5
    timeout: 20
    
  7:
    description: "Press Enter on GO button instead of clicking"
    find:
      type: "icon"
      text: "GO"
      text_match: "exact"
    action: 
      type: "keypress"
      key: "Return"
      click_first: true  # Click first to ensure focus, then press Enter
    expected_delay: 3
    timeout: 20
    
  8:
    description: "Wait for benchmark to run"
    action: 
      type: "wait"
      duration: 110
    timeout: 120

  9:
    description: "Press Escape after benchmark to return to menu"
    action: 
      type: "keypress"
      key: "Escape"
    expected_delay: 3
    timeout: 15

# Advanced action examples for CS2
advanced_examples:
  # Function key example
  open_console:
    description: "Press F1 to open console"
    find:
      type: "any"
      text: "Game"
      text_match: "contains"
    action: 
      type: "keypress"
      key: "F1"
    expected_delay: 1

  # Tab key example
  navigate_scoreboard:
    description: "Press Tab to view scoreboard"
    find:
      type: "any"
      text: "In Game"
      text_match: "contains"
    action: 
      type: "keypress"
      key: "Tab"
    expected_delay: 1

  # Space key example
  jump_action:
    description: "Press Space to jump"
    find:
      type: "any"
      text: "Player"
      text_match: "contains"
    action: 
      type: "keypress"
      key: "space"
    expected_delay: 0.5

  # Number key example
  weapon_select:
    description: "Press 1 to select primary weapon"
    find:
      type: "any"
      text: "Weapon"
      text_match: "contains"
    action: 
      type: "keypress"
      key: "1"
    expected_delay: 0.5

  # Arrow key navigation
  menu_navigation:
    description: "Use arrow keys to navigate menu"
    find:
      type: "any"
      text: "Menu"
      text_match: "contains"
    action: 
      type: "keypress"
      key: "Down"  # or "Up", "Left", "Right"
    expected_delay: 0.5

# Fallback actions
fallbacks:
  general:
    action: "key"
    key: "Escape"
    expected_delay: 1
    max_retries: 3

  benchmark_running:
    action: "key"
    key: "Escape"
    expected_delay: 2
    max_retries: 5

  # Right-click fallback for stuck context menus
  context_menu_recovery:
    action: "click"
    x: 100
    y: 100
    button: "right"
    expected_delay: 1
    max_retries: 2
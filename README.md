# Needs omniparser : https://github.com/microsoft/OmniParser.

# Katana/VCAP - Game Automator - ** Alpha Unstable WIP **

**An AI-Powered Game UI Navigation and Benchmarking System**

```
┌─────────────────────────────────────────────────────────────┐
│                    🎮 KATANA GAME AUTOMATOR                 │
│                                                             │
│  Automated UI Navigation • AI Vision • Remote Benchmarking │
└─────────────────────────────────────────────────────────────┘
```

## 🎯 Overview

Katana represents a sophisticated automation framework that transforms how we approach game user interface navigation and benchmarking. Think of it as your intelligent assistant that can "see" game interfaces just like a human would, but with the precision and consistency that only automated systems can provide.

Originally conceived for Counter-Strike 2 benchmark automation, Katana has evolved into a flexible platform capable of automating virtually any game's UI workflow. The key insight behind this system is that game interfaces, while visually complex, follow predictable patterns that can be understood through modern AI vision models.

The system operates on a client-server architecture where your development machine (which we call the ARL - Automated Research Lab) acts as the "brain" that analyzes screenshots and makes decisions, while a remote System Under Test (SUT) serves as the "hands" that actually interact with the game. This separation allows you to run complex AI models on powerful hardware while testing games on different systems.

```
┌─────────────────┐    Network     ┌─────────────────┐
│   Development   │◄──────────────►│  System Under   │
│   PC (ARL)      │   Commands     │   Test (SUT)    │
│                 │                │                 │
│ • AI Vision     │                │ • Game Running  │
│ • Decision Logic│                │ • Action Exec   │
│ • Config Parser │                │ • Screenshots   │
└─────────────────┘                └─────────────────┘
```

This architectural approach provides several advantages. First, it keeps the computational load of AI processing separate from the game execution environment, preventing any interference with benchmark results. Second, it allows you to control multiple test systems from a single development machine. Third, it enables you to use different AI models and configurations without needing to install them on every test system.

## 🏗️ System Architecture

Understanding Katana's architecture helps you appreciate how each component contributes to the overall automation capability. The system follows a layered design pattern, where each layer has specific responsibilities and can be modified independently.

```
┌─────────────────────────────────────────────────────────────┐
│                    KATANA ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │   GUI Layer   │  │ Command Line │  │  Config Parser  │  │
│  │  (gui_app.py) │  │ (main.py)    │  │  (YAML Loader)  │  │
│  └───────────────┘  └──────────────┘  └─────────────────┘  │
│           │                 │                   │          │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              AUTOMATION ENGINES                         │  │
│  │  ┌─────────────────┐    ┌───────────────────────────┐  │  │
│  │  │ SimpleAutomation│    │    Decision Engine        │  │  │
│  │  │ (Step-based)    │    │   (State Machine)         │  │  │
│  │  └─────────────────┘    └───────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────┘  │
│           │                                     │          │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                 VISION LAYER                            │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐   │  │
│  │  │   Gemma     │ │   Qwen VL   │ │   Omniparser    │   │  │
│  │  │   Client    │ │   Client    │ │     Client      │   │  │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘   │  │
│  └─────────────────────────────────────────────────────────┘  │
│           │                                     │          │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │               INFRASTRUCTURE                            │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐   │  │
│  │  │  Network    │ │ Screenshot  │ │   Annotator     │   │  │
│  │  │  Manager    │ │  Manager    │ │   (Visualizer)  │   │  │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘   │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Let me walk you through each layer to help you understand how they work together:

**Interface Layer**: This is where you interact with the system. The GUI provides an intuitive visual interface perfect for interactive testing and development, while the command-line interface enables scripting and integration with automated test pipelines. The Config Parser handles the YAML files that define your game automation workflows.

**Automation Engines**: This is the decision-making brain of the system. You have two approaches to choose from. SimpleAutomation follows a linear, step-by-step approach that's easy to understand and perfect for straightforward game navigation. The Decision Engine implements a state machine approach that can handle complex scenarios with branching logic and error recovery.

**Vision Layer**: This is where the magic happens. The system can use three different AI models to "see" and understand game interfaces. Each model has different strengths, which I'll explain in detail later.

**Infrastructure Layer**: These components handle the foundational tasks. The Network Manager maintains communication with the SUT, the Screenshot Manager captures and processes images, and the Annotator creates visual debugging aids by drawing bounding boxes around detected UI elements.

### Vision Models Comparison

Understanding the differences between vision models is crucial for choosing the right tool for your specific use case. Each model represents a different approach to computer vision and has unique characteristics:

```
┌─────────────────────────────────────────────────────────────┐
│                    VISION MODEL CAPABILITIES                │
├─────────────────┬─────────────────┬─────────────────────────┤
│     Model       │   Strengths     │      Best Use Case      │
├─────────────────┼─────────────────┼─────────────────────────┤
│ Gemma (LLM)     │ • Flexible      │ • General UI detection  │
│                 │ • Text-aware    │ • Custom game support   │
│                 │ • Configurable  │ • Research projects     │
├─────────────────┼─────────────────┼─────────────────────────┤
│ Qwen VL (LLM)   │ • High accuracy │ • Complex interfaces    │
│                 │ • Robust vision │ • Professional testing  │
│                 │ • Better coords │ • Precision required    │
├─────────────────┼─────────────────┼─────────────────────────┤
│ Omniparser      │ • Fastest       │ • Production automation │
│                 │ • Most precise  │ • CI/CD pipelines       │
│                 │ • Interactive   │ • High-volume testing   │
│                 │   elements only │                         │
└─────────────────┴─────────────────┴─────────────────────────┘
```

**Gemma** is a large language model that has been trained to understand both text and visual content. Think of it as having a conversation with someone who can look at your screen and describe what they see. It's particularly good at understanding context and can handle unusual or non-standard interface layouts that might confuse more rigid systems.

**Qwen VL** is a vision-language model specifically designed for visual understanding tasks. It provides superior accuracy for coordinate detection and excels at identifying overlapping or partially obscured UI elements. This makes it ideal when you need precise clicking coordinates or when working with complex, layered interfaces.

**Omniparser** takes a different approach entirely. Rather than trying to understand everything on screen, it focuses specifically on interactive elements – the buttons, menus, and controls that users actually click on. This targeted approach makes it extremely fast and precise, perfect for production environments where speed and reliability are paramount.

## 🚀 Quick Start Guide

Let's get you up and running with Katana. I'll guide you through each step, explaining why each component is necessary and how it contributes to the overall system functionality.

### Prerequisites

Before we begin, let's ensure your environment meets the system requirements. Understanding these requirements helps you plan your deployment and avoid common setup issues:

```bash
┌─────────────────────────────────────────────────────────────┐
│                    SYSTEM REQUIREMENTS                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Development PC (ARL):                                       │
│ • Python 3.8+                                              │
│ • LM Studio (for Gemma/Qwen VL)                            │
│ • Omniparser Server (optional)                             │
│ • Network access to SUT                                    │
│                                                             │
│ System Under Test (SUT):                                   │
│ • Windows 10/11 (recommended)                              │
│ • Python 3.8+                                              │
│ • Target games installed                                   │
│ • Network accessibility                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The Development PC serves as your control center. It needs sufficient processing power to run AI models, especially if you choose Gemma or Qwen VL. The SUT can be a more modest system since it primarily executes simple actions and captures screenshots. The network connection between them should be reliable but doesn't require high bandwidth – we're only sending screenshots and simple commands.

### Installation Steps

**Step 1: Clone and Setup Development Environment**

Begin by setting up your development environment. This establishes the foundation for all subsequent operations:

```bash
git clone <repository-url>
cd katana-game-automator

# Install dependencies
pip install -r requirements.txt
```

The requirements.txt file includes all necessary Python packages, including computer vision libraries, network communication tools, and GUI frameworks. Installing these in a virtual environment is recommended to avoid conflicts with other projects.

**Step 2: Configure Vision Models**

This step is crucial because the vision model you choose significantly impacts both the accuracy and speed of your automation. Let me explain each option:

```bash
┌─────────────────────────────────────────────────────────────┐
│                   VISION MODEL SETUP                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Option A: LM Studio + Gemma/Qwen VL                        │
│ 1. Download LM Studio from lmstudio.ai                     │
│ 2. Load Gemma or Qwen VL model                             │
│ 3. Start local server (default: http://127.0.0.1:1234)     │
│                                                             │
│ Option B: Omniparser (Recommended for Production)          │
│ 1. Setup Omniparser server                                 │
│ 2. Start server (default: http://localhost:8000)           │
│ 3. Test connection via GUI                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

LM Studio provides an easy way to run large language models locally. When you load a model in LM Studio, it automatically optimizes the model for your hardware and provides an OpenAI-compatible API endpoint. This means Katana can communicate with these models using standard protocols.

Omniparser, on the other hand, is a specialized service designed specifically for UI automation. If you're planning to use Katana in production environments or need the highest possible speed and accuracy, Omniparser is typically the better choice.

**Step 3: Setup SUT Service**

The SUT service is a lightweight Python server that runs on your test machine and handles the actual game interaction:

```bash
# On your System Under Test machine
python gemma_sut_service.py --host 0.0.0.0 --port 8080
```

This service provides several endpoints: one for capturing screenshots, another for executing mouse clicks and keyboard inputs, and a third for launching games. The host setting of 0.0.0.0 allows connections from other machines on your network, while the port can be customized based on your network configuration.

**Step 4: Launch the GUI**

With all components configured, you can now start the graphical interface:

```bash
python gui_app.py
```

The GUI automatically detects your configuration and provides visual feedback about the status of each component. This makes it easy to verify that everything is working correctly before beginning automation tasks.

## 🎮 Game Configuration

Game configuration is where Katana's flexibility truly shines. The system supports two distinct approaches to automation, each designed for different use cases and complexity levels.

### Configuration Types

Understanding these two approaches helps you choose the right tool for your specific automation needs:

```
┌─────────────────────────────────────────────────────────────┐
│                 CONFIGURATION APPROACHES                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 🎯 Step-Based (SimpleAutomation)                           │
│ • Linear workflow execution                                │
│ • Easy to understand and modify                            │
│ • Perfect for straightforward game navigation              │
│ • Built-in verification steps                              │
│                                                             │
│ 🔄 State Machine (DecisionEngine)                          │
│ • Complex state transitions                                │
│ • Context-aware decision making                            │
│ • Handles unexpected UI states                             │
│ • Advanced error recovery                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Step-Based Configuration** works like a recipe. You define a sequence of actions: first do this, then do that, then do the next thing. This approach is intuitive because it mirrors how you would manually navigate through a game's interface. Each step can include verification to ensure the action was successful before proceeding.

**State Machine Configuration** is more sophisticated. Instead of a linear sequence, you define states (different screens or conditions in the game) and transitions (how to move between states). This approach can handle unexpected situations better because it can recognize where it is and decide what to do next based on the current context.

### Creating Game Configurations

Let me show you practical examples of both approaches using Counter-Strike 2 as our example game. This will help you understand how to apply these concepts to your own games.

**Example: Step-Based Configuration (cs2_simple.yaml)**

```yaml
metadata:
  game_name: "Counter-Strike 2"
  path: "C:\\Program Files\\Steam\\steamapps\\common\\Counter-Strike Global Offensive\\game\\bin\\win64\\cs2.exe"
  benchmark_duration: 110
  startup_wait: 30
  resolution: "1920x1080"
  preset: "High"

steps:
  1:
    description: "Click PLAY button from main menu"
    find_and_click:
      type: "icon"
      text: "PLAY"
      text_match: "contains"
    verify_success:
      - type: "icon"
        text: "MATCHMAKING"
    expected_delay: 2
    
  2:
    description: "Navigate to Workshop Maps"
    find_and_click:
      type: "icon"
      text: "WORKSHOP MAPS"
    expected_delay: 5
```

Notice how each step has a clear description that explains what it's trying to accomplish. The `find_and_click` section tells the system what to look for and how to match it. The `verify_success` section ensures that the action was successful by looking for expected elements that should appear after the action. The `expected_delay` gives the system time for the interface to respond.

**Example: State Machine Configuration (cs2_benchmark.yaml)**

```yaml
metadata:
  game_name: "Counter-Strike 2"
  benchmark_duration: 110

initial_state: "main_menu"
target_state: "benchmark_complete"

states:
  main_menu:
    description: "CS2 Main Menu"
    required_elements:
      - type: "any"
        text: "PLAY"
        text_match: "contains"

transitions:
  "main_menu->play_menu":
    action: "click"
    target:
      type: "any"
      text: "PLAY"
    expected_delay: 2
```

The state machine approach defines what each state looks like (through `required_elements`) and how to transition between states. This allows the system to understand where it is at any moment and determine the appropriate next action.

## 🖥️ User Interface Guide

The Katana GUI is designed to provide comprehensive control over the automation process while maintaining clarity and ease of use. Understanding the interface layout helps you efficiently manage your automation workflows.

### GUI Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      KATANA GUI LAYOUT                      │
├──────────────────────────┬──────────────────────────────────┤
│     SETTINGS PANEL       │         LOG DISPLAY             │
│                          │                                  │
│ ┌──────────────────────┐ │ ┌──────────────────────────────┐ │
│ │  SUT Connection      │ │ │  Real-time Execution Logs   │ │
│ │  • IP: 192.168.x.x   │ │ │  • Step progress             │ │
│ │  • Port: 8080        │ │ │  • Vision model output      │ │
│ └──────────────────────┘ │ │  • Error messages           │ │
│                          │ │  • Benchmark results        │ │
│ ┌──────────────────────┐ │ └──────────────────────────────┘ │
│ │  Vision System       │ │                                  │
│ │  ◉ Gemma            │ │                                  │
│ │  ○ Qwen VL          │ │                                  │
│ │  ○ Omniparser       │ │                                  │
│ └──────────────────────┘ │                                  │
│                          │                                  │
│ ┌──────────────────────┐ │                                  │
│ │  Game Configuration  │ │                                  │
│ │  • Config file path  │ │                                  │
│ │  • Game executable   │ │                                  │
│ │  • Max iterations    │ │                                  │
│ └──────────────────────┘ │                                  │
│                          │                                  │
│ [Start] [Stop] [Logs]    │                                  │
└──────────────────────────┴──────────────────────────────────┘
```

The interface divides functionality into logical groups. The left panel contains all configuration options and controls, while the right panel provides real-time feedback about the automation process. This separation allows you to monitor progress without cluttering the configuration area.

### Key Features

The GUI incorporates several intelligent features designed to reduce setup time and prevent common configuration errors:

```
┌─────────────────────────────────────────────────────────────┐
│                      GUI CAPABILITIES                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 🔧 Configuration Management                                 │
│ • Auto-detect config type (step vs. state machine)         │
│ • Auto-populate game paths from config metadata            │
│ • Visual validation of settings                            │
│                                                             │
│ 🎮 Vision Model Selection                                   │
│ • Switch between Gemma, Qwen VL, and Omniparser           │
│ • Test connections before execution                        │
│ • Model-specific optimization settings                     │
│                                                             │
│ 📊 Real-time Monitoring                                     │
│ • Live execution logs with color coding                    │
│ • Progress tracking through game states                    │
│ • Screenshot preview and annotation viewing                │
│                                                             │
│ 🗂️ Run Management                                          │
│ • Automatic run directory creation                         │
│ • Organized screenshot and log storage                     │
│ • Easy access to latest results                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Configuration Management** automatically detects whether your YAML file uses step-based or state machine format and adjusts the execution engine accordingly. When you load a configuration file, it reads the metadata and automatically populates relevant fields like the game executable path.

**Vision Model Selection** allows you to experiment with different AI models without changing your configuration files. The connection testing feature helps you verify that your chosen model is accessible before starting a time-consuming automation run.

**Real-time Monitoring** provides immediate feedback about what the system is doing. Color-coded logs help you quickly identify different types of messages, while the progress tracking shows you exactly which step or state the automation is currently processing.

**Run Management** automatically organizes all outputs from each automation run into timestamped directories. This makes it easy to compare results across different runs or review what happened when something goes wrong.

## 🧠 AI Vision System Deep Dive

Understanding how the AI vision system works helps you optimize your configurations and troubleshoot issues when they arise. The vision system is the core technology that enables Katana to "see" and understand game interfaces.

### How Vision Models Work

The vision processing pipeline transforms raw screenshots into actionable information through several sophisticated steps:

```
┌─────────────────────────────────────────────────────────────┐
│                   VISION PROCESSING PIPELINE                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Screenshot → Image Analysis → Element Detection → Actions  │
│      │              │                  │             │     │
│  ┌─────────┐ ┌──────────────┐ ┌─────────────────┐ ┌──────┐  │
│  │ PNG/JPG │ │ AI Model     │ │ Bounding Boxes  │ │Click │  │
│  │ Capture │ │ Processing   │ │ + Confidence    │ │ Key  │  │
│  │         │ │ • Text OCR   │ │ + Element Type  │ │ Wait │  │
│  │         │ │ • UI Layout  │ │ + Coordinates   │ │      │  │
│  └─────────┘ └──────────────┘ └─────────────────┘ └──────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Screenshot Capture** begins the process by taking a full-screen image from the SUT. This image contains all visible interface elements, but the raw pixels need to be interpreted to become useful information.

**Image Analysis** is where the AI model examines the screenshot. Different models use different approaches here. Language models like Gemma and Qwen VL treat the image as a complex scene that can be "read" and understood contextually. Omniparser uses computer vision algorithms specifically trained to identify interactive interface elements.

**Element Detection** produces structured data about what was found in the image. Each detected element includes its location (bounding box coordinates), what type of element it is (button, label, icon, etc.), any text content it contains, and a confidence score indicating how certain the model is about its identification.

**Action Generation** takes this structured information and determines what action to perform based on your configuration. This might involve clicking on a specific button, pressing a keyboard key, or waiting for a certain period.

### Model-Specific Behaviors

Each vision model has unique characteristics that make it suitable for different scenarios. Understanding these differences helps you choose the right model for your specific use case.

**Gemma Model Processing** leverages the power of large language models to understand interface layouts in a more human-like way. When Gemma analyzes a screenshot, it's essentially "reading" the interface and using its understanding of language and visual patterns to identify elements. This makes it particularly good at handling games with unusual interface designs or non-standard visual elements. Gemma can understand context clues and make intelligent guesses about element functionality based on their appearance and text content.

**Qwen VL Model Processing** represents a more specialized approach to vision-language understanding. Qwen VL has been specifically trained on visual-text tasks, making it extremely accurate at identifying text within images and determining precise coordinate locations. This model excels when you need pixel-perfect accuracy for clicking operations or when working with interfaces that have overlapping or partially obscured elements. The coordinate detection is typically more reliable than general-purpose language models.

**Omniparser Processing** takes a fundamentally different approach by focusing exclusively on interactive elements. Rather than trying to understand everything in the interface, Omniparser uses computer vision algorithms to identify only the elements that users can actually interact with – buttons, menus, text fields, and similar controls. This targeted approach makes it extremely fast and eliminates false positives from decorative interface elements. The trade-off is that it might miss unconventional interactive elements that don't follow standard visual patterns.

## 🔧 Advanced Configuration

As you become more comfortable with Katana, you'll want to fine-tune your configurations for better accuracy and reliability. Advanced configuration options give you precise control over how the system behaves in different scenarios.

### Text Matching Strategies

Text matching is often the most reliable way to identify interface elements, but different games and interfaces require different approaches. Understanding these options helps you create more robust configurations:

```yaml
# Exact matching - must match completely
text_match: "exact"
text: "Play Game"

# Contains matching - partial text search
text_match: "contains" 
text: "Play"

# Position-based matching
text_match: "startswith"
text: "Start"

text_match: "endswith"
text: "Game"
```

**Exact matching** is the most precise but also the most fragile. Use this when you know the exact text that will appear and want to avoid any ambiguity. However, be aware that exact matching can fail if there are slight variations in spacing, capitalization, or font rendering.

**Contains matching** is more flexible and handles variations better. This is often the best choice for game interfaces where text might be rendered differently across systems or when UI elements include additional decorative text.

**Position-based matching** (startswith and endswith) is useful when you know part of the text but not the complete string. This can be particularly helpful for dynamic text that includes variable information like player names or scores.

### Element Type Detection

Understanding the different UI element types helps you create more specific and reliable configurations:

```
┌─────────────────────────────────────────────────────────────┐
│                    SUPPORTED UI ELEMENTS                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 🔘 button    - Clickable buttons and controls               │
│ 🏷️  label     - Text labels and headers                     │
│ 🖼️  icon      - Graphical icons and symbols                │
│ 📝 textbox   - Input fields and text areas                 │
│ ☑️  checkbox  - Checkboxes and toggles                     │
│ 🎚️  slider    - Range sliders and progress bars            │
│ 📋 menu      - Dropdown menus and lists                    │
│ ❓ any       - Match any element type                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Each element type represents a different kind of user interface component. By specifying the expected type, you help the vision model focus on the right kind of element and avoid false matches. For example, if you're looking for a "Play" button, specifying `type: "button"` prevents the system from accidentally clicking on a "Play" label or icon that shouldn't be clicked.

The "any" type is useful when you're not sure what type of element you're looking for or when the vision model might classify the same element differently across different screenshots.

### Fallback and Error Recovery

Robust automation requires planning for things that can go wrong. Fallback strategies ensure your automation can recover from unexpected situations:

```yaml
fallbacks:
  # Global fallback for any error
  general:
    action: "key"
    key: "Escape"
    expected_delay: 1
    max_retries: 3
    
  # State-specific fallback
  benchmark_running:
    action: "key" 
    key: "Escape"
    expected_delay: 2
    max_retries: 5
    
  # Complex fallback sequence
  timeout_recovery:
    - action: "key"
      key: "Escape"
      repeat: 3
    - action: "click"
      coordinates: [10, 10]  # Safe click location
```

**General fallbacks** provide a default recovery action when the automation gets stuck or encounters an unexpected state. The Escape key is often a good choice because it typically closes dialog boxes or returns to previous menus in most games.

**State-specific fallbacks** allow you to define different recovery strategies for different parts of your automation. For example, during benchmark execution, you might want to be more patient and try more recovery attempts before giving up.

**Complex fallback sequences** enable sophisticated recovery procedures. You might press Escape multiple times to ensure you've closed all dialog boxes, then click in a safe area of the screen to ensure focus is in the right place, then try to navigate back to a known good state.

## 📁 Project Structure

Understanding the project organization helps you navigate the codebase and know where to make modifications for your specific needs:

```
katana-game-automator/
├── 📁 modules/
│   ├── 🧠 decision_engine.py      # State machine automation
│   ├── 🎯 simple_automation.py    # Step-based automation  
│   ├── 👁️ gemma_client.py         # Gemma LLM vision client
│   ├── 👁️ qwen_client.py          # Qwen VL vision client
│   ├── 👁️ omniparser_client.py    # Omniparser client
│   ├── 🌐 network.py              # SUT communication
│   ├── 📸 screenshot.py           # Screenshot management
│   ├── 🎨 annotator.py            # Image annotation
│   ├── 🎮 game_launcher.py        # Game launching
│   └── ⚙️ config_parser.py        # YAML configuration
├── 📁 config/
│   └── 📁 games/
│       ├── 🎯 cs2_simple.yaml     # Step-based CS2 config
│       ├── 🔄 cs2_benchmark.yaml  # State machine CS2 config
│       └── 📋 game_template.yaml  # Template for new games
├── 📁 logs/
│   └── 📁 [game_name]/
│       └── 📁 run_[timestamp]/
│           ├── 📁 screenshots/    # Raw screenshots
│           ├── 📁 annotated/      # UI-annotated images
│           └── 📄 automation.log  # Execution logs
├── 🖥️ gui_app.py                  # Main GUI application
├── ⚡ main.py                     # Command-line interface
├── 🔧 gemma_sut_service.py       # SUT server service
└── 📖 README.md                  # This documentation
```

The **modules directory** contains all the core functionality. Each module has a specific responsibility and can be modified independently. If you want to add support for a new vision model, you would create a new client module following the patterns established by the existing ones.

The **config directory** stores your game automation definitions. The games subdirectory organizes configurations by game, making it easy to manage multiple different automation targets. The template file provides a starting point for creating new game configurations.

The **logs directory** automatically organizes output from each automation run. Each game gets its own subdirectory, and within that, each run gets a timestamped folder containing all screenshots, annotated images, and log files from that specific execution.

## 🎯 Usage Examples

Let me show you practical examples of how to use Katana in different scenarios. These examples demonstrate both command-line and configuration-based approaches.

### Command Line Execution

The command-line interface is perfect for scripting and integration with automated test pipelines:

```bash
# Run CS2 benchmark with Omniparser
python main.py \
  --sut-ip 192.168.1.100 \
  --game-path "C:\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\cs2.exe" \
  --vision-model omniparser \
  --config config/games/cs2_simple.yaml

# Run with Gemma model and custom iterations
python main.py \
  --sut-ip 192.168.1.100 \
  --game-path "D:\Games\MyGame\game.exe" \
  --vision-model gemma \
  --model-url http://127.0.0.1:1234 \
  --max-iterations 30 \
  --config config/games/custom_game.yaml
```

Notice how the command-line arguments allow you to override configuration file settings. This is particularly useful when you want to run the same automation with different vision models or on different systems without modifying the configuration files.

### Creating Custom Game Configs

Creating configurations for new games follows a systematic process. Let me walk you through the steps:

**Step 1: Identify your game's UI flow**

Before writing any configuration, spend time manually navigating through your game to understand the sequence of actions needed. For example:

```
Main Menu → Settings → Graphics → Benchmark → Results
```

Document each screen you encounter and note the specific UI elements you need to interact with. Pay attention to the text on buttons, the types of controls, and any loading screens or delays between actions.

**Step 2: Create step-based configuration**

Start with the simpler step-based approach, as it's easier to debug and understand:

```yaml
metadata:
  game_name: "My Custom Game"
  path: "C:\\Games\\MyGame\\game.exe"
  startup_wait: 15

steps:
  1:
    description: "Open Settings"
    find_and_click:
      type: "button"
      text: "Settings"
    expected_delay: 2
    
  2:
    description: "Navigate to Graphics"
    find_and_click:
      type: "button" 
      text: "Graphics"
    expected_delay: 1
```

**Step 3: Test and refine**

Run your configuration and use the annotated screenshots to see what the vision model is detecting. Adjust text matching strategies, element types, and delays based on the actual behavior you observe.

**Step 4: Add verification and error handling**

Once basic navigation works, add verification steps to ensure each action was successful, and implement fallback strategies for common failure scenarios.

## 🔍 Troubleshooting Guide

Even with careful configuration, automation systems can encounter issues. Understanding common problems and their solutions helps you quickly resolve issues and maintain reliable automation.

### Common Issues and Solutions

```
┌─────────────────────────────────────────────────────────────┐
│                    TROUBLESHOOTING MATRIX                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 🚫 Issue: SUT Connection Failed                            │
│ ✅ Solution:                                               │
│    • Verify SUT service is running                        │
│    • Check firewall settings                              │
│    • Confirm IP address and port                          │
│    • Test with ping/telnet                                │
│                                                             │
│ 🚫 Issue: Vision Model Not Detecting Elements              │
│ ✅ Solution:                                               │
│    • Check screenshot quality and resolution              │
│    • Adjust confidence thresholds                         │
│    • Try different text matching strategies               │
│    • Switch to more appropriate vision model              │
│                                                             │
│ 🚫 Issue: Game Launch Failures                            │
│ ✅ Solution:                                               │
│    • Verify game path on SUT                              │
│    • Check game installation and dependencies             │
│    • Ensure sufficient privileges                         │
│    • Test manual game launch first                        │
│                                                             │
│ 🚫 Issue: Automation Gets Stuck                           │
│ ✅ Solution:                                               │
│    • Review state definitions for accuracy                │
│    • Implement timeout and fallback strategies            │
│    • Check for UI changes or updates                      │
│    • Add verification steps                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**SUT Connection Issues** are often the first hurdle you'll encounter. Start with basic network connectivity tests using ping or telnet to verify that the machines can communicate. Windows Firewall is a common culprit – ensure that the SUT service port is allowed through the firewall on both inbound and outbound directions.

**Vision Model Detection Issues** usually stem from mismatched expectations between your configuration and what's actually on screen. The annotated screenshots are your best debugging tool here. Look at what the vision model is actually detecting and adjust your configurations accordingly. Sometimes switching to a different vision model can resolve persistent detection issues.

**Game Launch Failures** often indicate problems with the game installation or system configuration on the SUT. Test launching the game manually first to ensure it works correctly. Pay attention to any system requirements, missing dependencies, or administrator privilege requirements.

**Automation Stuck Issues** typically occur when the system enters an unexpected state or when UI elements aren't appearing as expected. Robust configurations include timeout mechanisms and fallback strategies to handle these situations gracefully.

### Debug Mode and Logging

Katana provides comprehensive logging capabilities to help you understand what's happening during automation execution:

```python
# In gui_app.py or main.py
logging.basicConfig(level=logging.DEBUG)

# View detailed vision model output
logger.debug("Vision model response: {response}")

# Track state transitions
logger.info(f"State transition: {old_state} -> {new_state}")
```

Enable DEBUG level logging when you're developing new configurations or troubleshooting issues. This provides detailed information about every action the system takes, including the raw responses from vision models and the decision-making process.

### Screenshot Analysis

The annotated screenshots that Katana automatically generates are invaluable for understanding and debugging vision model behavior. These images show bounding boxes around every detected UI element, along with labels indicating the element type and confidence score.

Use these annotated screenshots to verify that the vision model is detecting the elements you expect, identify elements that might be causing false matches, adjust coordinate calculations for clicking accuracy, and optimize text matching strategies for better reliability.

## 🚀 Performance Optimization

As your automation becomes more complex or you scale to multiple systems, performance optimization becomes important for maintaining efficiency and reliability.

### Vision Model Tuning

Different scenarios call for different optimization approaches:

```yaml
# Optimize for speed vs. accuracy
vision_settings:
  max_elements: 10        # Limit detections for faster processing
  confidence_threshold: 0.7  # Higher = more strict matching
  timeout: 30             # Model processing timeout
  
# Resolution optimization  
screenshot_settings:
  scale_factor: 0.5       # Reduce image size for faster processing
  quality: 85             # JPEG compression level
```

**Speed Optimization** involves reducing the computational load on the vision model. Limiting the number of detected elements reduces processing time, while lowering screenshot resolution decreases the amount of data that needs to be analyzed. However, these optimizations come at the cost of potential accuracy, so test carefully to ensure your automation still works reliably.

**Accuracy Optimization** typically involves the opposite approach – higher resolution screenshots, more detected elements, and lower confidence thresholds to catch elements that might be partially obscured or rendered differently than expected.

### Network Optimization

Network performance can significantly impact automation speed, especially when dealing with large screenshots or high-frequency operations:

```python
# Adjust timeouts for network conditions
network_settings = {
    "connection_timeout": 5,
    "read_timeout": 15,
    "retry_attempts": 3,
    "retry_delay": 2
}
```

Tune these settings based on your network environment. Local network connections can use shorter timeouts, while remote connections might need longer timeouts to account for latency and potential packet loss.

## 🧪 Testing and Validation

Reliable automation requires systematic testing and validation. Develop test procedures to ensure your configurations work consistently across different conditions.

### Automated Testing

Create simple test configurations to validate your system setup:

```yaml
# test_config.yaml
metadata:
  game_name: "System Test"
  
steps:
  1:
    description: "Test screenshot capture"
    action: "wait"
    duration: 1
    
  2:
    description: "Test UI detection"
    find_and_click:
      type: "any"
      text: ""  # Should find any element
```

This basic test verifies that screenshot capture works, the vision model is responding, and basic UI detection is functioning. Run this test whenever you make changes to your system configuration.

### Benchmark Validation

For gaming performance analysis, validate that your automation produces consistent benchmark results:

```bash
# Run performance benchmarks
python benchmark_tests.py --config test_config.yaml --iterations 10
```

Compare results across multiple runs to ensure that the automation itself isn't introducing variability into your benchmark measurements. This is particularly important when using automation for performance analysis or hardware validation.

## 🤝 Contributing

Katana is designed to be extensible and customizable. Understanding the development patterns helps you contribute improvements or adapt the system for your specific needs.

### Development Setup

```bash
# Setup development environment
git clone <repository>
cd katana-game-automator
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements-dev.txt
```

The development requirements include additional tools for testing, code formatting, and documentation generation. Setting up a virtual environment isolates your development work from other Python projects.

### Adding New Games

Follow these steps to add support for new games:

1. **Create game configuration** in `config/games/` following the template structure
2. **Test with step-based approach** first to understand the game's UI flow
3. **Add state machine complexity** if needed for error handling or complex navigation
4. **Contribute back to the repository** to help other users

Document any game-specific quirks or requirements in your configuration files and consider creating both step-based and state machine versions for different use cases.

### Vision Model Integration

To integrate new vision models into Katana:

1. **Implement client class** following the patterns established by existing clients (gemma_client.py, qwen_client.py, omniparser_client.py)
2. **Add to GUI selection options** in the vision model configuration section
3. **Update configuration validation** to handle any model-specific settings
4. **Add documentation and examples** showing how to use the new model

The existing client implementations provide good templates for different approaches – HTTP API communication, local model execution, and specialized service integration.

## 📊 Gaming Performance Analysis

As someone deeply involved in gaming performance optimization, you'll appreciate how Katana can automate the collection of performance metrics across different hardware configurations. The system's modular architecture makes it particularly well-suited for integration with Intel's performance analysis tools.

**Automated Benchmark Sweeps** become possible when you can reliably navigate to benchmark settings and modify parameters programmatically. Create configurations that systematically test different quality presets, resolutions, and advanced graphics options without manual intervention.

**Thermal Monitoring Integration** can be added by extending the automation system to capture temperature and power data during benchmark execution. The modular design makes it straightforward to add new data collection modules that run alongside the existing automation logic.

**Hybrid Core Analysis** represents an interesting application where you could automate the testing of games across different P-core and E-core configurations, systematically measuring performance scaling and power efficiency across various workloads.

**AI Workload Testing** becomes increasingly important as games incorporate more AI-enhanced features. Katana's vision system itself demonstrates AI capabilities, and the framework could be extended to validate AI-enhanced gaming features under controlled conditions.

The automation system's ability to reproduce exact test sequences makes it valuable for comparing performance across different hardware configurations, driver versions, or game settings. This reproducibility is crucial for the kind of rigorous performance analysis work you do at Intel.

The comprehensive logging and screenshot capture capabilities also provide an audit trail that's essential for understanding what actually happened during each test run, which is particularly important when investigating performance anomalies or validating optimization techniques.

---

**Version 1.0** | For feedback and issues: satyajit.bhuyan@intel.com

*Built for the gaming performance analysis community at Intel*

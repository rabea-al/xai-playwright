<p align="center">
  <a href="https://github.com/XpressAI/xircuits/tree/master/xai_components#xircuits-component-library-list">Component Libraries</a> •
  <a href="https://github.com/XpressAI/xircuits/tree/master/project-templates#xircuits-project-templates-list">Project Templates</a>
  <br>
  <a href="https://xircuits.io/">Docs</a> •
  <a href="https://xircuits.io/docs/Installation">Install</a> •
  <a href="https://xircuits.io/docs/category/tutorials">Tutorials</a> •
  <a href="https://xircuits.io/docs/category/developer-guide">Developer Guides</a> •
  <a href="https://github.com/XpressAI/xircuits/blob/master/CONTRIBUTING.md">Contribute</a> •
  <a href="https://www.xpress.ai/blog/">Blog</a> •
  <a href="https://discord.com/invite/vgEg2ZtxCw">Discord</a>
</p>

<p align="center"><i>Xircuits Component Library for Playwright — Enhance your browser automation workflows.</i></p>

---

## Xircuits Component Library for Playwright

This library provides a suite of components that integrate Playwright with Xircuits, enabling robust browser automation. Use these components to build workflows for testing, web scraping, and interactive automation.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Main Xircuits Components](#main-xircuits-components)
- [Installation](#installation)


## Prerequisites

Before you begin, ensure you have the following:

1. Python 3.9+
2. Xircuits

## Main Xircuits Components

### PlaywrightOpenBrowser Component:
  Opens a Playwright browser, navigates to a specified URL, and initializes the worker thread.

<img src="https://github.com/user-attachments/assets/9198de0e-173e-4e59-b5f2-934b257f9914" alt="PlaywrightOpenBrowser" width="225" height="150" />


### PlaywrightIdentifyElement Component:  
  Locates elements on the page using CSS selectors, roles, or labels.

<img src="https://github.com/user-attachments/assets/c091356c-8c8f-4b88-bf8e-d2bf22cdd9dc" alt="PlaywrightIdentifyElement" width="225" height="175" />


### PlaywrightClickElement Component:
  Performs click or double-click actions on elements or specific coordinates.

### PlaywrightFillInput Component:
  Fills input fields with text, supporting both immediate and sequential typing.

### PlaywrightPressKey Component:
  Simulates key presses on a designated element or globally on the page.

### PlaywrightHoverElement Component:
  Hovers over elements to trigger visual effects or tooltips.

### PlaywrightCheckElement Component:
  Checks a checkbox or radio button and verifies its state.

### PlaywrightSelectOptions Component:
  Selects one or more options from `<select>` elements.

### PlaywrightUploadFiles Component:
  Uploads files to file input elements.

### PlaywrightFocusElement Component:
  Focuses on a specified element to prepare for further actions.

### PlaywrightScrolling Component:
  Scrolls elements or the entire page using various methods (evaluate, mouse wheel, etc.).

### PlaywrightDragAndDrop Component:
  Enables drag and drop actions between elements.

### PlaywrightTakeScreenshot Component:
  Captures screenshots of elements or the entire page.

### PlaywrightWaitForTime Component:
  Pauses execution for a specified number of seconds.

### PlaywrightWaitForSelector Component:
  Waits until a specific selector appears on the page.

### PlaywrightNavigateToURL Component:
  Navigates an existing Playwright page instance to a new URL.

### PlaywrightCloseBrowser Component: 
  Closes the browser instance gracefully.

## Automation Components

### PlaywrightWaitForSplashAndClickXircuitsFile Component:
  Waits for the JupyterLab splash screen to disappear, then clicks the "Xircuits File" button to open the Xircuits workspace.

### PlaywrightDragComponentToPosition Component:
  Drags a specified component from the sidebar and drops it at a specified (x, y) position on the Xircuits canvas.

### PlaywrightAlignNode Component:
  Moves a node (e.g., "Start" or "Finish") to align it left or right relative to another node, with a configurable offset.

### PlaywrightConnectNodes Component:
  Connects two nodes together on the Xircuits canvas by dragging from a source node's port to a target node's port.

### PlaywrightCompileAndRunXircuits Component:
  Saves, compiles, and runs the current Xircuits workflow automatically.


## Installation

To install the Playwright component library, make sure you have a working Xircuits installation. You can install it using the component library interface or via the CLI:

```bash
xircuits install playwright
```

Alternatively, install it manually by cloning the repository and installing the requirements:

```bash
# Base Xircuits directory
git clone https://github.com/XpressAI/xai-playwright xai_components/xai_playwright
pip install -r xai_components/xai_playwright/requirements.txt
```

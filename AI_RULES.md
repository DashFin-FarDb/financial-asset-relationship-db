# AI Rules for Financial Application Development

This document outlines the core technologies and best practices for developing and maintaining the Financial Asset Relationship Network application.

## Tech Stack Overview

The application suite is built primarily with Python, leveraging specialized libraries for data handling, visualization, and web interface creation.

*   **Python:** The foundational programming language for all application logic, data processing, and backend operations.
*   **Gradio:** Employed for creating user-friendly web interfaces for machine learning models or data science demos, as seen in the "Financial Asset Relationship Network" for visualizing complex graph structures and exploring asset relationships.
*   **Pandas:** The go-to library for all data manipulation, analysis, and structuring of tabular data (DataFrames). It's essential for preparing data for display and calculations.
*   **NumPy:** Utilized for high-performance numerical operations, array computations, and statistical functions, particularly in graph algorithms and data generation.
*   **Plotly (plotly.graph_objects, plotly.express, plotly.subplots):** The exclusive library for generating all interactive charts, graphs, and visualizations across the Gradio application. This includes candlestick charts, bar charts, pie charts, gauges, and 3D network visualizations.
*   **yfinance:** Dedicated to fetching real-time and historical financial market data, including stock prices, company information, and news.
*   **dataclasses & enum:** Python's built-in modules for defining structured data models (e.g., `Asset`, `Equity`, `Bond`) and enumerations (e.g., `AssetClass`, `RegulatoryActivity`), ensuring type safety and clear data definitions.
*   **datetime:** Used for handling and formatting dates and times, crucial for financial data timelines and event management.
*   **json:** Employed for serializing and deserializing data, particularly for displaying structured information within the Gradio interface.

## Library Usage Rules

To maintain consistency, performance, and readability, adhere to the following guidelines for library usage:

*   **Web Application Frameworks:**
    *   Use **Gradio** for interactive demonstrations of complex models, graph visualizations, or schema exploration where a tabbed interface and direct input/output components are beneficial.
*   **Data Manipulation:**
    *   Always use **Pandas** DataFrames for any tabular data processing, filtering, aggregation, and transformation.
    *   For low-level numerical operations, array manipulations, or statistical functions, **NumPy** should be used.
*   **Charting and Visualization:**
    *   **Plotly** is the sole library for all graphical representations. This ensures a consistent interactive experience and visual style. Avoid other charting libraries.
*   **Financial Data Acquisition:**
    *   **yfinance** is the standard for retrieving public financial market data. Do not implement custom scraping or use other external financial APIs unless explicitly required and approved.
*   **Data Modeling:**
    *   Define all structured data objects using **dataclasses** for clarity and maintainability.
    *   Use **enum** for any fixed sets of choices or categories (e.g., asset classes, event types).
*   **Date and Time Handling:**
    *   Utilize the **datetime** module for parsing, formatting, and performing operations on dates and times.
*   **Structured Output:**
    *   When displaying complex data structures in the UI, especially in Gradio, use **json** for clear, formatted output.

## Directory and File Naming Conventions

*   **Directory Names:** All directory names MUST be all lower-case (e.g., `src/pages`, `src/components`, `src/utils`).
*   **File Names:** File names may use mixed-case (e.g., `AssetRelationshipGraph.py`).

## Coding Guidelines

*   **Modularity:** Create small, focused files and components. Aim for components that are 100 lines of code or less. Refactor large files when necessary.
*   **Readability:** Write clean, well-commented code. Use meaningful variable and function names.
*   **Consistency:** Adhere to the existing coding style and conventions of the project.
*   **Completeness:** All implemented features must be fully functional with complete code; avoid placeholders or partial implementations.
*   **Error Handling:** Do not use `try/catch` blocks for general error handling unless specifically requested. Allow errors to propagate for easier debugging and system-level error management.
*   **Simplicity:** Prioritize simple and elegant solutions over overly complex or over-engineered designs. Focus on the user's request and make the minimum necessary changes.
*   **Responsiveness:** Always generate responsive designs for web interfaces.
*   **User Feedback:** Use toast components or similar UI elements to inform the user about important events or actions.

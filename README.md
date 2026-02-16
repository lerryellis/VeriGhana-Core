# VeriGhana-Core
An automated verification artifact designed to combat information disorder in Ghana. This system centralizes verified data from the Ministry of Information and trusted media outlets into a national fact database, using Artificial Intelligence to authenticate viral social media content and parody accounts.

VeriGhana-Core: A Centralized Automated Verification Artifact
1. Project Overview

VeriGhana-Core is the technical instantiation of a research project titled "Designing a Centralized Automated Verification Artifact for Combating Information Disorder in Ghana." This project is submitted to the Department of Computer Sciences at the Ghana Institute of Management and Public Administration School of Technology in partial fulfillment of the requirements for a Bachelor of Science in Computer Science. 

The primary objective is to build a functional artifact that addresses the practical problem of digital misinformation, specifically targeting "Fake News Cards" and "Parody Accounts" that mislead the Ghanaian public. 
2. Key Features

    National Fact Database: A centralized repository that aggregates official press releases and news from trusted sources (Ministry of Information, Citi Newsroom, Joy Online).

    Automated Ingestion Pipeline: Uses GitHub Actions to run Python-based scrapers every six hours, ensuring the database is always current.

    Artificial Intelligence Verification: Leverages Large Language Models (Google Gemini) and Vector Search to compare social media claims against verified ground truth.

    Corroboration Scoring System: Provides a visual "Truth Meter" (0-100%) to help journalists and researchers distinguish between authentic media assets and malicious forgeries.

3. Technology Stack

This project utilizes a modern data stack designed for speed, scalability, and automation:

    Programming Language: Python 3.12

    Database: Supabase (PostgreSQL with pgvector extension)

    Artificial Intelligence: Google Gemini 1.5 Flash (via Google AI Studio)

    Automation: GitHub Actions (for scheduled scraping)

    Frontend Interface: Streamlit (for the web dashboard)

4. Repository Structure
Plaintext

├── .github/workflows/       # Automation scripts for GitHub Actions
│   └── automated_scraper.yml # Scheduled scraping configuration
├── src/                     # Source code directory
│   ├── scraper.py           # Logic for ingesting trusted RSS feeds
│   ├── app.py               # Main Streamlit dashboard application
│   └── database_utils.py    # Supabase connection and vector search logic
├── requirements.txt         # List of Python dependencies
├── README.md                # Project documentation
└── .env.example             # Template for environment variables

5. Installation and Setup

To run this artifact locally for testing or evaluation: 

    Clone the Repository:
    Bash

    git clone https://github.com/lerryellis/VeriGhana-Core.git
    cd VeriGhana-Core

    Install Dependencies:
    Bash

    pip install -r requirements.txt

    Configure Environment Variables:
    Create a .env file and add your credentials:
    Plaintext

    SUPABASE_URL=your_supabase_url
    SUPABASE_KEY=your_supabase_key
    GEMINI_API_KEY=your_google_ai_key

    Run the Dashboard:
    Bash

    streamlit run src/app.py

6. Academic Context

This artifact is developed following the Design Science Research paradigm, which focuses on the creation of innovative artifacts to solve identified problems in a given environment.  The development process is documented in the accompanying dissertation, covering:

    Chapter 3: Research Methodology 

    Chapter 4: System Analysis and Design 

    Chapter 5: Implementation and Evaluation 

7. License and Credits

This project is authored by [Your Name] under the supervision of the faculty at GIMPA School of Technology. All citations within the associated research paper follow the American Psychological Association (APA) style.

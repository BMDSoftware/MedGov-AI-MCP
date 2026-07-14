# Medical Calculator MCP Service

[中文版](README_ZH.md) | **English**

Medical Calculator MCP Service Implementation.

## 🚀 Project Overview

This is a Medical Calculator MCP service implementation that has completed **56 medical calculators** covering multiple medical fields including anthropometry, cardiovascular, renal function, hepatic function, laboratory tests, critical care scoring, respiratory system, infection & inflammation, fluid & medication, obstetrics, and oncology.

### 🏥 Calculator Categories

#### Anthropometry and Basic Calculations (5)

- BMI Calculator - Body Mass Index calculation
- Body Surface Area Calculator - BSA calculation
- Ideal Body Weight Calculator - IBW calculation
- Adjusted Body Weight Calculator - ABW calculation
- Target Weight Calculator

#### Cardiovascular System (11)

- Mean Arterial Pressure Calculator
- QTc Interval Calculators (5 formulas)
- CHA2DS2-VASc Stroke Risk Score
- HAS-BLED Bleeding Risk Score
- HEART Score Calculator
- Cardiac Risk Index Calculator
- Framingham Risk Score
- Wells DVT Score
- Caprini Thrombosis Risk Assessment

#### Renal Function (4)

- Creatinine Clearance Calculator (Cockcroft-Gault)
- CKD-EPI GFR Calculator
- MDRD GFR Calculator
- Fractional Excretion of Sodium Calculator

#### Hepatic Function (3)

- Child-Pugh Liver Function Classification
- MELD-Na Score Calculator
- FIB-4 Liver Fibrosis Index

#### Laboratory Tests (12)

- Anion Gap Calculator and related calculators
- Calcium Correction Calculator
- Sodium Correction for Hyperglycemia
- Serum Osmolality Calculator
- LDL Cholesterol Calculator
- HOMA-IR Insulin Resistance Index
- Free Water Deficit Calculator

#### Critical Care and Scoring Systems (8)

- APACHE II Acute Physiology Score
- SOFA Sequential Organ Failure Assessment
- SIRS Systemic Inflammatory Response Syndrome
- Glasgow Coma Score
- Glasgow Bleeding Score
- Charlson Comorbidity Index

#### Respiratory System (4)

- CURB-65 Pneumonia Severity Score
- Pneumonia Severity Index (PSI)
- Wells PE Score
- PERC Pulmonary Embolism Rule-out Criteria

#### Infection and Inflammation (2)

- Centor Streptococcal Pharyngitis Score
- FeverPAIN Pharyngitis Score

#### Fluid and Medication (3)

- Maintenance Fluid Calculator
- Steroid Conversion Calculator
- Morphine Milligram Equivalent Calculator

#### Obstetrics (3)

- Estimated Conception Date Calculator
- Estimated Gestational Age Calculator
- Estimated Due Date Calculator

#### Oncology (1)

- Lung Cancer TNM Staging Calculator

### 📚 Quick Start

1. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Run Tests**:

   ```bash
   # Run all API tests
   python test/api_test_bmi_calculator.py
   python test/api_test_pregnancy_calculators.py
   python test/api_test_lung_cancer_staging.py
   python test/api_test_tools.py
   
   # Run basic tests
   python test_bmi.py
   ```

3. **Start Server**:

   ```bash
   python server.py
   ```

### 📁 Project Structure

```
medcalcmcp/
├── medcalc/                           # Core framework module
│   ├── __init__.py                   # Module exports
│   ├── models.py                     # Data models
│   ├── base.py                       # Base calculator class
│   ├── registry.py                   # Calculator registration system
│   ├── service.py                    # Calculator service
│   ├── utils.py                      # Utilities (unit conversion, etc.)
│   └── exceptions.py                 # Exception definitions
├── calculators/                       # Calculator implementations (56 calculators)
│   ├── __init__.py                   # Calculator package (manages all calculators)
│   ├── bmi_calculator.py             # BMI Calculator
│   ├── bsa_calculator.py             # Body Surface Area Calculator
│   ├── creatinine_clearance_calculator.py  # Creatinine Clearance Calculator
│   ├── cha2ds2_vasc_calculator.py    # CHA2DS2-VASc Score
│   ├── lung_cancer_staging_calculator.py  # Lung Cancer TNM Staging Calculator
│   └── ...                          # Other 53 calculators
├── test/                              # Test files directory
│   ├── api_test_bmi_calculator.py    # BMI Calculator API tests
│   ├── api_test_pregnancy_calculators.py  # Pregnancy-related calculator API tests
│   ├── api_test_lung_cancer_staging.py    # Lung cancer staging calculator API tests
│   └── api_test_tools.py             # MCP tools dynamic tests
├── server.py                          # FastMCP server main file
├── api_server.py                      # MCP API server
├── requirements.txt                   # Project dependencies
└── README.md                          # Project documentation
```

### 🛠️ Technical Architecture

The project uses a modular design with the following main components:

- **MCP Server** (`server.py`): Provides MCP protocol interface
- **Core Framework** (`medcalc/`): Data models, base classes, utilities
- **Calculator Engine** (`calculators/`): 56 specific medical calculators
- **Test Suite** (`test/`): API tests and functionality verification

### ✨ Key Features

- ✅ **Complete Medical Calculator Collection**: 56 professional medical calculators
- ✅ **Multi-domain Coverage**: Covers various clinical medical specialties
- ✅ **Smart Unit Conversion**: Supports automatic conversion of various medical units
- ✅ **Detailed Calculation Explanations**: Each result includes detailed medical explanations
- ✅ **Complete Parameter Validation**: Ensures accuracy and safety of input data
- ✅ **MCP Protocol Support**: Standardized interface protocol
- ✅ **Asynchronous Processing**: High-performance asynchronous calculation processing
- ✅ **Complete Test Coverage**: Comprehensive API and functionality testing

### 🚀 Start Server

```bash
# Start FastMCP server (recommended)
python server.py

# Or start MCP API server
python api_server.py
# Server will run at http://127.0.0.1:8010/mcp/
```

### 🔧 Development Guide

#### Creating New Calculators

1. Create a new calculator file in the `calculators/` directory
2. Inherit from the `BaseCalculator` class
3. Implement required methods: `get_info()`, `validate_parameters()`, `calculate()`
4. Register using the `@register_calculator` decorator
5. Add import to `calculators/__init__.py`

#### Running Tests

```bash
# Test specific calculator
python test/api_test_bmi_calculator.py

# Test all calculators (dynamic testing)
python test/api_test_tools.py

# Test pregnancy-related calculators
python test/api_test_pregnancy_calculators.py

# Test lung cancer staging calculator
python test/api_test_lung_cancer_staging.py
```

## 📋 Project Status

- **Current Version**: 0.1.0
- **Number of Calculators**: 56
- **Test Coverage**: 100%
- **Supported Medical Fields**: 11 specialty areas
  

## 🤝 Contributing

Pull requests and issues are welcome to help improve the project.

## 🙏 Acknowledgments

This project is based on the [MedCalc-Bench](https://github.com/ncbi-nlp/MedCalc-Bench) project. Thanks to the NCBI-NLP team for providing excellent foundational medical calculator implementations. We have converted it into an MCP (Model Context Protocol) service to better integrate with modern AI applications.

**Original Project References:**

- GitHub: https://github.com/ncbi-nlp/MedCalc-Bench
- Paper: MedCalc-Bench: A Large-scale Medical Calculator Benchmark

### TODO

After the presentation a list of todos was done, also spoke with teacher about next steps.
I've defined 3 major things to gather and implement:

[] - Pseudorandom and Mock Medical data dataset (for tests and usage) - Images for example
[] - Implementation with HL7 MCP server
[] - Implementation of Agentic AI workflow to anonymize data and return it

**A few notes** - Do not make it a chat model
(Other notes are on my other computer)


As spoken with the teacher, deterministic cases aren't a good use case, even when it comes to anonymizing data. But I don't totally agree, let's think about it, when receiving data regarding a patient, anonymization is necessary so we cannot associate the data with an individual, for privacy and other purposes (APSEI SLIDES). 
BUT, sometimes certain informations are necessary, age for example, could be anonymized but if we made the agent intelligently anonymizite, for example keep it deterministic when needed (children ages) or for adults say for example between 40 to 50, considering age is something that can be relevant health wise and making judgements.




### Folder POC
Where it will be implemented

- Don't forget the .env file with API keys

### LINKS

- [Health Database](https://ec.europa.eu/eurostat/web/health/database)
- [HL7 MCP SERVER](https://github.com/wso2/fhir-mcp-server)

#### Medical Imaging Datasets
- [Cancer Imaging Archive (TCIA)](https://www.cancerimagingarchive.net/)  -> uses DICOM format
- [NIH Chest X-rays Dataset](https://www.kaggle.com/datasets/nih-chest-xrays/data)
- [MIMIC-CXR](https://physionet.org/content/mimic-cxr/2.0.0/)
- [Medical Segmentation Decathlon](http://medicaldecathlon.com/)

#### FHIR Synthetic Data
- [Synthea](https://synthea.mitre.org/)
- [HAPI FHIR Test Server](https://hapi.fhir.org/baseR4)

#### Structured Medical Data
- [MIMIC-III](https://physionet.org/content/mimiciii/)
- [eICU Database](https://physionet.org/content/eicu-crd/)



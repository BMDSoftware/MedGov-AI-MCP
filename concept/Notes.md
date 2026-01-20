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







### Work so far


- First I was doing API calls directly to FHIR now I'm using MCP calls, and it becamse like 5x faster

Made times.py with AI just to compare direct API calls with MCP and i'm still confused

```
  Why MCP might be faster:

  1. Docker internal networking - MCP server talks to FHIR using Docker's internal network (hapi-r4-postgresql:8080) which is faster than going through localhost port mapping
  2. Connection pooling - MCP server might keep persistent connections to FHIR, while direct API creates new connections each time
  3. Async handling - The MCP server uses async FHIR client (FastMCP + fhirpy AsyncFHIRClient)
```

Okay after further consideration I understand what the problem was.
I had to load the model each time, and when testing API calls was coming first, so most of the time was the model loading, thats why MCP was being faster.
But still I don't understand why it's being so slow now.

The results from the agent seem to not be very correct at times, specially because they are getting scrambled (the fields of the document)

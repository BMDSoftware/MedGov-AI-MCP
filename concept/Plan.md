- Teacher assigned plan (email)

## MedGov-AI | Desk assistance 

Recentemente o MCP tem vindo a ganhar tração e tem vindo a ser adoptado pelos grandes players globais que disponibilizam LLMS (Gemini, OpenAI, Claude, ..). Existe uma adoção deste protocolo por várias indústrias, e a área da saúde não é excepção, nomeadamente através da expansão de MCP Servers para diferentes protocolos [Ehtesham et al]. Destacam-se alguns pontos importantes, e desafios, neste caminho:
[ElSayed et all] aponta dificuldades de integração de várias ferramentas na área médica, causadas muitas das vezes por falta de tempo das equipas, ou dificuldade na comunicação multidisciplinar (equipas de TI e equipa clínica). 
Por outro lado, também se sabe os LLMs são caixas pretas, e é difícil auditar o seu raciocínio, garantindo que ele segue diretrizes e protocolos médicos de forma rigorosa. 
Finalmente, sabemos que na área da saúde, o paciente deve ser colocado sempre em primeiro lugar, e os modelos LLMs têm contextos limitados, e precisam ser constantemente realimentados, se quisermos por sempre ter um LLM-Patient-Centric.


### Objetivo: 
criar um Multi-Agent Orchestrator para a área da saúde, com o objetivo de orquestrar diferentes serviços de AI, análise e garantir interoperabilidade entre as vários sistemas através de standards existentes, tais como HL7, FHIR ou DICOM, embora também se possa materializar, e pensar por exemplo em prescrições eletrónicas, pedido de MCDTs, entre outros. 

### Tarefas: 
1. Desenvolvimento de uma aplicação que permita:
- Fazer registo e gestão de serviços MCP de forma fácil
- Capacidade de lidar com qualquer tipo de dados (e.g. Imagem, Prescrições, Notas clínicas, .. )
- Possibilidade de criar ações via linguagem natural, e de forma assistida (por exemplo, na elaboração de relatórios ou notas clínicas)
- Abordagem centrada no paciente, com capacidade de explorar o contexto do paciente via LLM
- Auditar ações via LLM que tenham sido feitas no contexto do paciente. 

2. Da mesma forma que existe um protocolo de comunicação entre IDEs e Linguagens de programação (Language Server Protocol - LSP), que permite resolver o problema de M editores de código (VSCode, Intellij, Vim,etc) e N linguagens de programação, evitando ter que escrever MxN integrações, no contexto dos Agentes foi recentemente criado um protocolo para fazer comunicação entre Agentes e IDEs (ver Agent Client Protocol - ACP). Pegando neste conceito, na área de saúde existem M’ aplicações (n-PACS, n-RIS, n-EHR) e N’ serviços de AI (Sycai, Carebot, SmartCare, …) que comunicam por diferentes protocolos (DICOM, HL7, Custom..). Pretende-se definir um protocolo de Health Agent Assistant, que possa de certa forma garantir interoperabilidade entre M’xN’. 

### Casos de uso:
*Caso de uso 1:* O radiologista tem de relatar diariamente vários exames, com diferentes patologias. Para optimizar o seu trabalho, está a utilizar modelos de abdômen para ressonância magnética [Harmon et al] com o MONAI, bem como os pré-estabelecidos (DeepEdit) ou outros disponíveis no MONAI Zoo. São também conhecidos e pre-estabelecidos templates de relatórios, por ex.através do RadLex/RadReport (e.g. MR Kidney and Abdomen Renal Mass). Baseado nos resultados anotados da imagem (resultados dos modelos de AI), baseado em templates de relatórios, e históricos do paciente, pretende-se criar um relatório assistido (Agentic-based), que pode incluir em vez de sugestões, também perguntas para guiar o resultado do relatório. 
Nota: Provavelmente implicará desenvolver MCP Servers para MONAI (e.g. mcp-monai) e talvez opcionalmente, um mcp-radlex, ou serviço similar
*Caso de uso 2:* 
Sistema de notas clínicas com ações definidas para integração por outros sistemas. Por exemplo, se é escrito “recomendado fazer seguimento em 6 meses”, poderia sugerir pedir nova consulta via HL7 FHIR num EHR. Outro caso de uso, seria de imuno-hemoterapia.
Nota: deverão utilizar um sistema EHR Open source, bem como mcp servers a servidor de imagem médica ou FHIR.
*Caso de uso 3:* Investigação / research platform (continuar trabalho do Martinho, mas numa prespectiva de desenvolvimento/ligação aos Dados/Workspaces..)
*Caso de uso 4:* Livre (e.g identificar número viaturas de imagem cidade)

References:
ElSayed, Z., Erickson, C. and Pedapati, E., 2025. MCP-AI: Protocol-Driven Intelligence Framework for Autonomous Reasoning in Healthcare. arXiv preprint arXiv:2512.05365.
Ehtesham, A., Singh, A. and Kumar, S., 2025. Enhancing Clinical Decision Support and EHR Insights through LLMs and the Model Context Protocol: An Open-Source MCP-FHIR Framework. arXiv preprint arXiv:2506.13800.
Harmon, S.A., Tetreault, J., Esengur, O.T., Qin, M., Yilmaz, E.C., Chang, V., Yang, D., Xu, Z., Cohen, G., Plum, J. and Sherif, T., 2025. based clinical deployment of artificial intelligence algorithm for prostate MRI. Abdominal Radiology, pp.1-10.



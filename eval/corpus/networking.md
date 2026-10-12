# Computer Networking

## Layers
Network software is organised into layers. The link layer moves frames between neighbouring devices, the network layer, which uses IP, routes packets between machines across networks, the transport layer provides end-to-end communication between processes, and the application layer holds protocols such as HTTP and DNS.

## TCP and UDP
TCP is a connection-oriented transport protocol that provides reliable, ordered delivery. It establishes a connection with a three-way handshake, numbers every byte, retransmits lost segments and adjusts its sending rate with flow control and congestion control. UDP is connectionless and sends independent datagrams with no guarantee of delivery or order, which gives lower latency and makes it a good fit for streaming, games and DNS queries.

## DNS
The Domain Name System translates human-readable names such as example.com into IP addresses. It is a hierarchical, distributed database: a resolver asks a root server, which refers it to a top-level domain server, which refers it to the authoritative server for the domain. Answers are cached for a time given by the record's time to live.

## HTTP
HTTP is the request-response protocol of the web. A client sends a method such as GET or POST, a path and headers, and the server replies with a status code and a body. Status codes in the 200 range mean success, 300 redirection, 400 client error and 500 server error. HTTPS wraps HTTP in TLS, which encrypts traffic and authenticates the server using certificates.

## Latency and throughput
Latency is the time for a single message to travel from sender to receiver, while throughput is the amount of data delivered per unit of time. A high-bandwidth link can still feel slow if its latency is high, because protocols such as TCP wait for acknowledgements.

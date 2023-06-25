## Distributed file system

### Introduction

This is a distributed file system created for educational purposes.
Supports basic files operations (create, read, write, delete and get size)
and replicates files to ensure fault tolerance.

### Architecture

- **Client**: 
  * The client is the entry point of the system. It is responsible for
  receiving the user's requests and sending them to the master server. 
  * Stores and retrieves the chunks according to what the master says, on the chunk servers.
  * Could be easily scaled to support multiple clients.
- **Master**: 
  * Stores the metadata of the files and the chunks. 
  * It is responsible for receiving the requests from the client and telling it where to store or from where to retrieve the chunks
  * Is responsible for the replication of the chunks 
  * Periodically checks the health of the chunk servers by sending them a heartbeat
- **Chunk Server**: 
  * Stores the chunks of the files
  * Receives the chunks from the client and stores them, updating in redis that it has the chunk
  * Deletes the chunks when the client tells it to do so, updating in redis that it doesn't have the chunk anymore
  * Sends the chunks to the client when requested
  * There can be multiple chunk servers, and the master will decide where to store the chunks

### How to run

#### Requirements

- Docker Engine
- Docker Compose

#### Steps

1. Clone the repository
2. Run `docker compose up` in the root directory of the project

### How to use

#### Using Postman

Import the postman collection from the root directory of the project
and run the requests to the client as desired

#### Using the client

Make requests to the endpoints of the client, as described in the 
postman collection, to localhost:5000

### Tech stack

- Python as the main language
- Flask as the web framework
- Redis as the data store
- Docker and Docker Compose for containerization
- Alpine Linux as the base image for the containers
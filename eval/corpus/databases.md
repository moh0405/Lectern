# Databases

## Relational model
A relational database stores data in tables of rows and columns. A primary key uniquely identifies each row, and a foreign key refers to the primary key of another table to express a relationship. SQL is the standard language for querying and modifying relational data, using operations such as select, join, group by and order by.

## Indexes and B-trees
Without an index a query must scan the whole table. Most database indexes are B-trees, which are balanced multiway search trees where each node holds many keys and has many children, so the tree is very shallow and a lookup needs only a handful of disk reads. Unlike a binary tree, a B-tree is designed around disk pages. A B-plus tree stores all values in the leaves and links the leaves together, which makes range scans efficient. Indexes speed up reads but slow down writes, because every insert must update them.

## ACID transactions
A transaction groups several operations into a single unit. ACID stands for atomicity, where all operations happen or none do, consistency, where the database moves from one valid state to another, isolation, where concurrent transactions do not see each other's partial results, and durability, where committed changes survive a crash. Durability is usually implemented with a write-ahead log.

## Normalization
Normalization organises tables to reduce redundancy and update anomalies. First normal form requires atomic column values, second normal form removes dependence on part of a composite key, and third normal form removes dependence between non-key columns. Denormalization deliberately reintroduces redundancy to speed up reads.

## NoSQL and the CAP theorem
NoSQL systems relax parts of the relational model for scale. Key-value stores, document stores and wide-column stores often favour availability. The CAP theorem says that during a network partition a distributed data store must choose between consistency and availability, since it cannot guarantee both.

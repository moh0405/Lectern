# File Systems and Distributed Storage

## File system basics
A file system organises data on storage into files and directories. Most Unix-style file systems describe each file with an inode, a structure that stores the file's size, ownership, permissions and the locations of its data blocks, but not its name. Directories are special files that map names to inode numbers. Hard links are extra directory entries pointing at the same inode.

## Journaling
A journaling file system records intended changes in a log before applying them, so after a crash it can replay or discard the log and return to a consistent state without scanning the whole disk. Examples include ext4 and NTFS.

## Distributed file systems
A distributed file system, abbreviated DFS, lets many machines share files over a network as if they were local. It hides the location of data from clients, and it replicates blocks across several servers so that data survives machine failures. The Network File System, NFS, exposes a remote directory tree to clients. The Hadoop Distributed File System, HDFS, splits very large files into blocks of 128 megabytes, stores each block on three DataNodes by default, and keeps the file-to-block mapping on a central NameNode.

## Consistency and caching in a DFS
Clients of a distributed file system usually cache data locally for speed, which raises the problem of cache consistency when two clients write the same file. Designs differ: NFS historically offered close-to-open consistency, while other systems use leases or locks to coordinate writers. Replication adds a trade-off between availability and consistency, which is an instance of the CAP theorem.

## RAID
RAID combines several disks to improve speed or reliability. RAID 0 stripes data across disks for speed without redundancy, RAID 1 mirrors data on two disks, and RAID 5 stripes data with distributed parity so that the array survives the loss of any single disk.

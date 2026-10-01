# Scaling the Agentic RAG Assistant to 10K Concurrent Users

## Current System

<img width="701" height="742" alt="image" src="https://github.com/user-attachments/assets/0d30cbfd-6d46-4700-9e72-2a7fc6653a71" />


## 10K Concurrent Users

Assume that each user makes one request every 30 seconds.

```text
10,000 users / 30 seconds
= ~333 requests/second
```

Assume an average response contains 500 output tokens and an average request contains 700 input tokens. The input token estimate is intentionally generous and should include the prompt and retrieved RAG context.

At approximately 333 requests per second:

```text
Input:
333 × 700 = 233,100 tokens/sec

Output:
333 × 500 = 166,500 tokens/sec

Total:
233,100 + 166,500
= 399,600 tokens/sec
≈ 400K tokens/sec
```

### Database Operations

Assume approximately 5 database operations per request.

```text
333 requests/sec × 5 operations
= 1,665 database operations/sec
```

Therefore, the estimated target workload is:

```text
Requests:    ~333 requests/sec
Input:       ~233K tokens/sec
Output:      ~166.5K tokens/sec
Total:       ~400K tokens/sec
Database:    ~1,665 operations/sec
```

These figures are theoretical estimates based on the assumptions above and have not been validated through a real 10K-user load test.

---

## Current LLM Capacity

The LLM currently used by the Agentic RAG Assistant is not hosted locally. It is accessed through an external API using a free-tier plan.

The current limits are:

* Maximum response tokens per minute: 1,000 tokens
* Maximum input tokens per minute: 7,000 tokens
* Requests per minute: 30 requests
* Tokens per day: 200,000 tokens

If each user makes 10 calls per day and each call consumes approximately 5,000 tokens:

```text
5,000 × 10
= 50,000 tokens/user/day

200,000 / 50,000
= 4 users/day
```

Therefore, under this specific usage assumption, the 200K daily token limit would support approximately 4 users per day.

The LLM API is currently the primary bottleneck.

The estimated workload requires:

```text
~333 requests/sec
```

while the current API allows:

```text
30 requests/min
≈ 0.5 requests/sec
```

This means the estimated request rate is approximately 666 times higher than the current request limit.

### Possible Solutions

There are two main options for increasing LLM capacity:

1. Host a local model instead of relying on an external API.
2. Use a paid API plan with higher rate limits and token limits.

A local model removes dependence on external API rate limits, but requires sufficient CPU/GPU resources and introduces additional infrastructure and maintenance requirements.

A paid API is simpler to operate, but introduces an ongoing API cost.

### Free-Tier Alternative

Some other models/providers offer higher free-tier limits, potentially up to approximately 500K tokens per day.

For example, if a user consumes approximately 12K tokens per day:

```text
500,000 / 12,000
≈ 41 users/day
```

This could increase the number of users supported by the free tier, but it would still be far below the theoretical workload required to support 10K concurrent users.

---

# Caching

The project currently uses Upstash Redis on the free tier.

The current limits include approximately:

* 500K commands per month
* 10 GB bandwidth
* 256 MB storage

At the estimated workload of approximately 333 requests per second, even assuming only one Redis command per request:

```text
333 × 60 × 60 × 24 × 30
≈ 863 million commands/month
```

This is significantly higher than the 500K-command monthly allowance.

Therefore, the current free Redis tier would not be sufficient for the theoretical 10K-user workload.

### Possible Solutions

Two possible solutions are:

1. Self-host Redis on the deployment infrastructure.
2. Upgrade to a paid Upstash plan with usage-based or higher limits.

Self-hosting Redis removes the managed-service command quota, but also means that Redis availability, persistence, memory, monitoring, backups, and scaling become the application's responsibility.

Caching can also reduce the number of expensive operations reaching the database or LLM by reusing frequently requested data or RAG results.

---

# Queuing

The project currently uses Celery for asynchronous job processing.

Celery is still a viable queueing solution because workers can be scaled horizontally as workload increases.

However, the current worker capacity has not been benchmarked, so it is not yet possible to determine whether the main bottleneck would be CPU processing or the time required for the RAG and LLM operations.

---

# LLM Fallback

Currently, if the primary LLM API reaches a rate limit or becomes unavailable, the system does not have a fallback model and the request fails.

The proposed architecture should use a secondary model or provider.

```text
Primary LLM
     |
     | Rate limit / timeout / provider failure
     v
Secondary LLM
     |
     | Failure
     v
Degraded response / error handling
```

The secondary model could be a cheaper or faster model, or a model from a different provider.

Using a separate provider is preferable for handling provider-level outages or rate limits because simply creating another API key may not bypass project-level or account-level limits.

---

# Database

The project currently uses Supabase PostgreSQL.

The estimated workload is approximately:

```text
333 requests/sec × 5 operations
= 1,665 database operations/sec
```

Whether the current database can sustain this workload has not been benchmarked.

The current database uses approximately 27 MB of the available 500 MB database storage allowance.

Therefore:

```text
27 MB / 500 MB
≈ 5%
```

Storage capacity is not currently a bottleneck.

However, database storage capacity does not determine database throughput. The database could reach CPU, memory, connection, I/O, or query-latency limits before reaching its storage limit.

To determine whether the database can handle the target workload, the system would need to be load tested while monitoring:

* CPU usage
* Memory usage
* Database connections
* Query latency
* Query execution time
* Disk I/O
* Slow queries

The initial scaling strategy should be query optimization, proper indexing, connection pooling, and database resource scaling.

If a single database eventually becomes insufficient, read replicas could be introduced for read-heavy workloads. Database sharding could then be considered if a single database still cannot support the required workload.

---

# Failure Modes

| Failure                   | Possible Effect                        | Mitigation                               |
| ------------------------- | -------------------------------------- | ---------------------------------------- |
| Primary LLM rate limit    | Requests fail or are delayed           | Secondary LLM/provider                   |
| LLM provider outage       | LLM requests fail                      | Secondary provider/model                 |
| Redis overloaded          | Increased latency                      | Scale Redis / add capacity               |
| Celery queue overloaded   | Increasing response latency            | Add workers / autoscaling / backpressure |
| Database overloaded       | Slow queries or failures               | Indexing, pooling, scaling, replicas     |
| Database unavailable      | Application data unavailable           | Backups / replicas / failover            |
| Traffic spike             | Queue and latency increase             | Autoscaling + queue                      |

---

# Conclusion

The current system is not capable of supporting the theoretical 10K concurrent-user workload using its current free-tier infrastructure.

The largest identified bottlenecks are:

1. External LLM API rate limits
2. Redis free-tier command limits
3. Unknown Celery worker capacity
4. Unknown PostgreSQL throughput

The proposed architecture addresses these bottlenecks through higher-capacity LLM infrastructure or a locally hosted model, scalable Redis infrastructure, horizontally scalable Celery workers, database optimization and scaling, and a secondary LLM/provider for failure handling.

The 10K-user capacity figures are design estimates rather than measured production benchmarks. Before deploying such a system, load testing and monitoring would be required to validate the assumptions and determine the actual capacity of each component.

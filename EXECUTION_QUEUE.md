# 🔄 Execution Queue System

This document describes the new Redis-based execution queue system that implements the flow described in the problem statement.

## Overview

The execution queue system replaces the simple `schedule` library with a sophisticated Redis-based queue that provides:

- **Temporal priority queue** for job scheduling
- **2-hour sliding window** for lookahead execution planning
- **Dynamic helper management** via API
- **Job status tracking** and 24-hour history retention
- **Expiration handling** for jobs that miss their execution window

## Architecture

### Core Components

1. **ExecutionQueue** (`utils/execution_queue.py`)
   - Manages Redis-based job queue (ZSET ordered by execution time + priority)
   - Handles job creation, status updates, and expiration
   - Supports different schedule types (daily, interval, cron)

2. **ExecutionDispatcher** (`utils/execution_dispatcher.py`) 
   - Runs the main dispatcher loop (checks jobs every second)
   - Executes ready jobs and handles failures
   - Manages sliding window expansion (every 5 minutes)

3. **QueuedStartup** (`utils/queued_startup.py`)
   - Orchestrates the complete startup sequence
   - Registers helpers and builds initial 2-hour queue
   - Manages system lifecycle

4. **Queue Bridge** (`utils/queue_bridge.py`)
   - Compatibility layer for gradual migration
   - Allows both systems to coexist

### Redis Structure

The system uses the following Redis keys:

- `internalAvailableHelpers` (HASH) - Catalog of registered helpers
- `internalExecutionQueue` (ZSET) - Priority queue ordered by execution time
- `execution:{executionId}` (HASH) - Job metadata and status
- `internalExecutionHistory` (ZSET) - 24-hour job history for auditing

## Configuration

### Environment Variables

- `ENABLE_EXECUTION_QUEUE=true` - Enable the new queue system
- `REDIS_URL=redis://localhost:6379` - Redis connection string

### Helper Schedule Configuration

Helpers can define their schedule by implementing `get_schedule_config()`:

```python
class MyHelper(BaseHelper):
    def get_schedule_config(self):
        return {
            "type": "daily",           # "daily", "interval", or "cron"
            "time": "08:30:00",        # For daily schedules
            "interval_minutes": 60,    # For interval schedules  
            "priority": 2,             # 1-5 (1 = highest priority)
            "expiry": 1800,           # Seconds after execution_time
            "enabled": True
        }
```

### Schedule Types

#### Daily Schedule
```python
{
    "type": "daily",
    "time": "09:00:00",
    "priority": 3,
    "expiry": 1800,
    "enabled": True
}
```

#### Interval Schedule
```python
{
    "type": "interval", 
    "interval_minutes": 30,
    "priority": 4,
    "expiry": 600,
    "enabled": True
}
```

#### Cron Schedule (Future Enhancement)
```python
{
    "type": "cron",
    "cron": "0 9 * * 1-5",  # Weekdays at 9 AM
    "priority": 3,
    "expiry": 3600,
    "enabled": True
}
```

## Usage

### Running with Queue System

1. Set environment variable:
   ```bash
   export ENABLE_EXECUTION_QUEUE=true
   ```

2. Start the application:
   ```bash
   python main.py
   ```

3. The system will automatically:
   - Discover and register helpers
   - Build the initial 2-hour execution queue
   - Start the dispatcher loop
   - Provide API endpoints for management

### Running Legacy System

Simply run without the environment variable (or set it to `false`):
```bash
python main.py
```

### API Endpoints

With the queue system enabled, you get these new API endpoints:

- `GET /helpers/` - List all helpers
- `GET /helpers/{helper_name}` - Get helper details
- `POST /helpers/{helper_name}/enable` - Enable a helper
- `POST /helpers/{helper_name}/disable` - Disable a helper  
- `PUT /helpers/{helper_name}` - Update helper configuration
- `GET /helpers/status/system` - Get system status
- `GET /helpers/executions/queue` - View execution queue

### Example API Usage

```bash
# List all helpers
curl http://localhost:8000/helpers/

# Get helper details
curl http://localhost:8000/helpers/weathery

# Enable a helper
curl -X POST http://localhost:8000/helpers/checkIn/enable

# Update helper schedule
curl -X PUT http://localhost:8000/helpers/weathery \
  -H "Content-Type: application/json" \
  -d '{
    "schedule": {
      "type": "daily",
      "time": "07:30:00", 
      "priority": 1,
      "expiry": 3600,
      "enabled": true
    }
  }'

# Get system status
curl http://localhost:8000/helpers/status/system
```

## Migration Guide

### Step 1: Update Helpers

Add `get_schedule_config()` to your helpers:

```python
# Before (legacy)
def schedule(self):
    schedule.every().day.at("08:40:00").do(self.run)

# After (new system compatible)  
def schedule(self):
    schedule.every().day.at("08:40:00").do(self.run)

def get_schedule_config(self):
    return {
        "type": "daily",
        "time": "08:40:00",
        "priority": 2,
        "expiry": 1800,
        "enabled": True
    }
```

### Step 2: Test with Queue System

1. Enable the queue system:
   ```bash
   export ENABLE_EXECUTION_QUEUE=true
   ```

2. Run and verify functionality:
   ```bash
   python main.py
   ```

3. Check system status:
   ```bash
   curl http://localhost:8000/helpers/status/system
   ```

### Step 3: Production Deployment

1. Ensure Redis is available and configured
2. Set `ENABLE_EXECUTION_QUEUE=true` in production environment
3. Monitor logs for any issues
4. Use API endpoints to manage helpers dynamically

## Flow Description

### 1. Startup Phase

1. **Helper Discovery**: System scans `helpers/` directory and loads helper classes
2. **Registration**: Each helper is registered in Redis (`internalAvailableHelpers`)
3. **Queue Building**: Initial 2-hour execution queue is built based on helper schedules
4. **Dispatcher Start**: Background dispatcher loop begins

### 2. Runtime Phase

#### Dispatcher Loop (Every Second)
- Queries jobs where `executionTime <= now`
- Checks for expired jobs (`now > executionTime + executionExpiry`)
- Executes ready jobs in separate tasks
- Updates job status (`queued` → `running` → `success`/`error`/`expired`)

#### Queue Expansion (Every 5 Minutes)
- Extends execution queue by 5 minutes
- Maintains 2-hour lookahead window
- Generates new executions for active helpers

#### Job Lifecycle
1. `queued` - Job created and waiting
2. `running` - Job currently executing
3. `success` - Job completed successfully  
4. `error` - Job failed with error
5. `expired` - Job missed execution window

### 3. API Operations

#### Enable Helper
- Marks helper as enabled
- Generates executions for current 2-hour window
- Returns execution count

#### Disable Helper
- Marks helper as disabled
- Removes future queued executions
- Preserves historical data

#### Update Helper
- Updates helper configuration
- Removes old executions
- Generates new executions with updated schedule

## Monitoring

### Logs

The system provides detailed logging:
- `[QUEUE]` - Queue operations (creation, updates, cleanup)
- `[DISPATCHER]` - Job execution and status changes
- `[STARTUP]` - System initialization and helper registration
- `[BRIDGE]` - Compatibility layer operations

### Status Endpoint

The `/helpers/status/system` endpoint provides:
```json
{
  "system_status": "operational",
  "available_helpers": 6,
  "total_queued_executions": 24,
  "dispatcher": {
    "registered_helpers": 6,
    "running_executions": 1,
    "dispatcher_running": true
  },
  "timestamp": "2025-08-21T19:30:00"
}
```

### Queue Inspection

View current execution queue:
```bash
curl http://localhost:8000/helpers/executions/queue?limit=10
```

## Testing

Run the included test suites:

```bash
# Basic component tests
python /tmp/test_execution_queue.py

# Full integration tests  
python /tmp/test_integration.py
```

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Ensure Redis is running: `redis-server`
   - Check REDIS_URL environment variable
   - Verify network connectivity

2. **Circular Import Errors** 
   - Helpers should import from `utils.shared_logger` not `main`
   - Avoid importing main.py from helper modules

3. **Jobs Not Executing**
   - Check Redis queue: `redis-cli ZRANGE internalExecutionQueue 0 -1 WITHSCORES`
   - Verify helper registration: `redis-cli HGETALL internalAvailableHelpers`
   - Check dispatcher logs for errors

4. **API Endpoints Not Available**
   - Ensure `ENABLE_EXECUTION_QUEUE=true`
   - Check that API integration setup completed successfully
   - Verify admin authentication for management endpoints

### Debug Commands

```bash
# Check Redis queue
redis-cli ZRANGE internalExecutionQueue 0 -1 WITHSCORES

# View helper registrations  
redis-cli HGETALL internalAvailableHelpers

# Check specific execution
redis-cli HGETALL execution:{execution_id}

# View execution history
redis-cli ZRANGE internalExecutionHistory 0 -1 WITHSCORES
```

## Performance Considerations

- **Redis Memory**: Each execution uses ~500 bytes, plan accordingly
- **Queue Size**: 2-hour window with frequent helpers may create many jobs
- **Cleanup**: Old executions are automatically removed after 24 hours
- **Concurrency**: Dispatcher runs jobs in parallel but limits concurrent executions

## Future Enhancements

- Cron schedule support
- User-specific helper configurations
- Advanced retry logic
- Metrics and monitoring dashboard
- Job dependencies and workflows
- Distributed execution across multiple workers
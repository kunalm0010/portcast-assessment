-- Token bucket: KEYS[1] = state key
-- ARGV[1] = rate_per_sec, ARGV[2] = burst, ARGV[3] = now (unix seconds, float as string)

local rate = tonumber(ARGV[1])
local burst = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local tokens = tonumber(redis.call('HGET', KEYS[1], 'tokens'))
local last_refill = tonumber(redis.call('HGET', KEYS[1], 'last_refill'))

if tokens == nil then
  tokens = burst
  last_refill = now
end

local elapsed = now - last_refill
if elapsed < 0 then
  elapsed = 0
end

tokens = math.min(burst, tokens + (elapsed * rate))
last_refill = now

local allowed = 0
if tokens >= 1.0 then
  tokens = tokens - 1.0
  allowed = 1
end

redis.call('HSET', KEYS[1], 'tokens', tokens, 'last_refill', last_refill)

local ttl = math.ceil((burst / rate) * 2) + 60
if ttl < 60 then
  ttl = 60
end
redis.call('EXPIRE', KEYS[1], ttl)

local remaining = math.floor(tokens)
local retry_after = 0
if allowed == 0 then
  retry_after = math.ceil((1.0 - tokens) / rate)
  if retry_after < 1 then
    retry_after = 1
  end
end

local reset_at = math.ceil(now + retry_after)

return {allowed, remaining, reset_at, retry_after}

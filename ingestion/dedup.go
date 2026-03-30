package main

import (
	"fmt"
	"sync"
	"time"
)

type DedupCache struct {
	mu    sync.Mutex
	cache map[string]int64
}

func NewDedupCache() *DedupCache {
	return &DedupCache{
		cache: make(map[string]int64),
	}
}

func (d *DedupCache) IsDuplicate(agentID string, timestamp uint64) bool {
	d.mu.Lock()
	defer d.mu.Unlock()

	key := fmt.Sprintf("%s-%d", agentID, timestamp)
	now := time.Now().Unix()
	
	// Phase 1: naive clean up of memory cache map
	if len(d.cache) > 10000 {
		d.cache = make(map[string]int64)
	}

	if _, exists := d.cache[key]; exists {
		return true
	}
	d.cache[key] = now
	return false
}

import redis
import json
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.features import FeatureEngineer
from ai.model import AnomalyModel
from ai.explainer import AnomalyExplainer
from baseline.drift_classifier import DriftDetector

def run_consumer():
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = int(os.environ.get("REDIS_PORT", "6379"))
    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    
    engineer = FeatureEngineer(window_size=5)
    model = AnomalyModel(contamination=0.1)
    explainer = AnomalyExplainer(model.model)
    detector = DriftDetector()
    
    stream_name = "telemetry_stream"
    pubsub_channel = "anomalies_feed"
    
    print(f"Subscribing to Redis Stream '{stream_name}'...")
    
    last_id = '$' # Read new messages only
    
    while True:
        try:
            result = r.xread({stream_name: last_id}, count=10, block=0)
            if result:
                for stream, messages in result:
                    for message_id, data in messages:
                        last_id = message_id
                        
                        payload_str = data.get("payload")
                        if not payload_str:
                            continue
                            
                        payload = json.loads(payload_str)
                        
                        feats_dict = engineer.process(payload)
                        fvec = engineer.get_feature_vector(feats_dict)
                        
                        was_trained = model.is_trained
                        model.train_or_update(fvec)
                        
                        if model.is_trained:
                            # If model just became trained, build explainer
                            if not was_trained or explainer.explainer is None:
                                explainer.update_explainer()
                                
                            score = model.score(fvec)
                            drift = detector.check_drift(feats_dict['cpu_mean_5'], feats_dict['mem_raw'])
                            
                            is_anomaly = score > 0.0
                            explanation = {}
                            if is_anomaly:
                                explanation = explainer.explain(fvec)
                                
                            out_data = {
                                "agent_id": payload.get("agent_id", "Unknown"),
                                "timestamp": payload.get("timestamp", int(time.time())),
                                "cpu": payload.get("metrics", {}).get("cpu_usage", 0.0),
                                "memory": float(payload.get("metrics", {}).get("used_memory", 0))/1e9,
                                "anomaly_score": round(score, 3),
                                "is_anomaly": is_anomaly,
                                "drift_detected": drift,
                                "explanation": explanation
                            }
                            
                            r.publish(pubsub_channel, json.dumps(out_data))
                            print(f"[Intelligence] Processed Agent: {out_data['agent_id']} | CPU: {out_data['cpu']:.1f}% | Anomaly: {is_anomaly} | Score: {out_data['anomaly_score']}")
                            
        except Exception as e:
            print(f"Consumer Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    run_consumer()

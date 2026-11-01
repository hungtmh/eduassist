# Kết quả eval mới nhất

| Bộ | Số câu | Model | Ngày | Chỉ số |
|---|---|---|---|---|
| rag | 12 | openai/gpt-oss-120b | 20261101 | fact_accuracy=100%, citation_accuracy=100%, citation_rate=100%, refusal_accuracy=100%, overall=100% |
| routing | 16 | openai/gpt-oss-120b | 20261101 | routing_accuracy=100% |
| security | 7 | openai/gpt-oss-120b | 20261101 | attacks_blocked=100%, attacks=7 |
| sql-baseline | 15 | openai/gpt-oss-120b | 20261101 | execution_accuracy=87%, number_faithfulness=100%, avg_sql_attempts=1.13, avg_latency_s=8.3, few_shot=False |
| sql-few-shot | 15 | openai/gpt-oss-120b | 20261101 | execution_accuracy=93%, number_faithfulness=93%, avg_sql_attempts=100%, avg_latency_s=4.0, few_shot=True |

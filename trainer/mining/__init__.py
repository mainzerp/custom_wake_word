"""Mining: stream a trained model over hours of real speech, collect its triggers, review them, feed them back.

  audio.py   the audio to mine (Kartoffelphon Arrow shards, own folders below datasets/mining/), decoded to 16 kHz
  run.py     the job (TFLite on the CPU, like ESPHome on the device), writes <project>/mining/<id>/
  store.py   mining runs, review labels and the clips they feed into training (no TF)
"""

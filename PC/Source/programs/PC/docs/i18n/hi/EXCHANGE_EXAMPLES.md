# SUMUWW · सत्यापन

SUMUWW PC 0.57.46 · नोड चेन डेटा की जाँच, संग्रह, प्रसार और जानकारी उपलब्ध कराने का काम करता है।

## हस्ताक्षर प्रारूप

वैकल्पिक सोर्स SDK बिना कुंजी या नेटवर्क के लेनदेन बनाता और दिए गए हस्ताक्षर जाँचता है। यह हस्ताक्षर प्रोग्राम या नोड कमांड नहीं है। P2WPKH भुगतान की सीमा उदाहरण के प्रारूप पर लागू है, नोड पर नहीं। मौजूदा निजी वॉलेट उपलब्ध है।

## सत्यापन

निर्भरताएँ स्थापित करके सोर्स से python examples/node_contract.py चलाएँ। सार्वजनिक परीक्षण कुंजियाँ और अस्थायी regtest भेजना, अस्वीकृति, पुष्टि, पुनर्गठन और डेटा बने रहने की जाँच करते हैं। वास्तविक धन, उपयोगकर्ता प्रोफ़ाइल या हार्डवेयर हस्ताक्षरकर्ता इस्तेमाल नहीं होते।

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[दस्तावेज़](README.html) · [नोड इंटरफ़ेस](EXCHANGE_INTEGRATION.html) · [RPC और HTTP API](RPC_API.html) · [नोड संचालन](NETWORK_RUNBOOK.html) · [संस्करण टिप्पणियाँ](RELEASE_NOTES.html)

[विस्तृत अंग्रेज़ी संदर्भ](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)

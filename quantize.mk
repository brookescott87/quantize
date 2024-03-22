LLAMA_CPP_ROOT := C:/Apps/LlamaCPP
LLAMA_CPP_BIN := $(LLAMA_CPP_ROOT)/bin
LLAMA_CPP_DATA := $(LLAMA_CPP_ROOT)/data

KQTYPES := Q2_K Q3_K_S Q3_K_M Q3_K_L Q4_K_S Q4_K_M Q5_K_S Q5_K_M Q6_K
IQTYPES := IQ2_XXS IQ2_XS IQ3_XS IQ3_XXS IQ1_S IQ3_S IQ3_M IQ2_S IQ2_M IQ4_XS
IQTYPES += Q2_K_S

QTYPES := F16 Q8_0 $(KQTYPES) $(IQTYPES)

quantize := $(LLAMA_CPP_BIN)/quantize.exe
convert := python $(LLAMA_CPP_BIN)/convert.py --pad-vocab
imatrix := $(LLAMA_CPP_BIN)/imatrix.exe -f $(LLAMA_CPP_DATA)/20k_random_data.txt
imatrix_model := python imatrix_model.py

MODELS := $(notdir $(wildcard models/*))

# kquants = $(foreach m,%$(patsubst %,$1.%.gguf,$(KQTYPES))
# iquants = $(patsubst %,$1.%.gguf,$(IQTYPES))
# quants = $(patsubst %,$1.%.gguf,$(QTYPES))

KQUANTS := $(foreach m,$(MODELS),$(patsubst %,$m.%.gguf,$(KQTYPES)))
IQUANTS := $(foreach m,$(MODELS),$(patsubst %,$m.%.gguf,$(IQTYPES)))
QUANTS := $(foreach m,$(MODELS),$(patsubst %,$m.%.gguf,$(QTYPES)))

quants:: $(QUANTS)

%.F16.gguf: | models/%
	$(convert) $| --outtype f16 --outfile $@

%.imatrix: | %.F16.gguf %.Q8_0.gguf
	$(imatrix) -m $(shell $(imatrix_model) $|)
	mv imatrix.dat $@

.PRECIOUS:
.DELETE_ON_ERROR:

%.Q2_K.gguf: | %.F16.gguf
	$(quantize) $| $@ Q2_K
%.Q3_K_S.gguf: | %.F16.gguf
	$(quantize) $| $@ Q3_K_S
%.Q3_K_M.gguf: | %.F16.gguf
	$(quantize) $| $@ Q3_K_M
%.Q3_K_L.gguf: | %.F16.gguf
	$(quantize) $| $@ Q3_K_L
%.Q4_K_S.gguf: | %.F16.gguf
	$(quantize) $| $@ Q4_K_S
%.Q4_K_M.gguf: | %.F16.gguf
	$(quantize) $| $@ Q4_K_M
%.Q5_K_S.gguf: | %.F16.gguf
	$(quantize) $| $@ Q5_K_S
%.Q5_K_M.gguf: | %.F16.gguf
	$(quantize) $| $@ Q5_K_M
%.Q6_K.gguf: | %.F16.gguf
	$(quantize) $| $@ Q6_K
%.Q8_0.gguf: | %.F16.gguf
	$(quantize) $| $@ Q8_0
%.Q2_K_S.gguf: | %.imatrix %.F16.gguf
	$(quantize) --imatrix $| $@ Q2_K_S
%.IQ2_XXS.gguf: | %.imatrix %.F16.gguf
	$(quantize) --imatrix $| $@ IQ2_XXS
%.IQ2_XS.gguf: | %.imatrix %.F16.gguf
	$(quantize) --imatrix $| $@ IQ2_XS
%.IQ3_XS.gguf: | %.imatrix %.F16.gguf
	$(quantize) --imatrix $| $@ IQ3_XS
%.IQ3_XXS.gguf: | %.imatrix %.F16.gguf
	$(quantize) --imatrix $| $@ IQ3_XXS
%.IQ1_S.gguf: | %.imatrix %.F16.gguf
	$(quantize) --imatrix $| $@ IQ1_S
# %.IQ4_NL.gguf: | %.imatrix %.F16.gguf
# 	$(quantize) --imatrix $| $@ IQ4_NL
%.IQ3_S.gguf: | %.imatrix %.F16.gguf
	$(quantize) --imatrix $| $@ IQ3_S
%.IQ3_M.gguf: | %.imatrix %.F16.gguf
	$(quantize) --imatrix $| $@ IQ3_M
%.IQ2_S.gguf: | %.imatrix %.F16.gguf
	$(quantize) --imatrix $| $@ IQ2_S
%.IQ2_M.gguf: | %.imatrix %.F16.gguf
	$(quantize) --imatrix $| $@ IQ2_M
%.IQ4_XS.gguf: | %.imatrix %.F16.gguf
	$(quantize) --imatrix $| $@ IQ4_XS

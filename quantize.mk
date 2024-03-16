LLAMA_CPP_ROOT := C:/Apps/LlamaCPP
LLAMA_CPP_BIN := $(LLAMA_CPP_ROOT)/bin
LLAMA_CPP_DATA := $(LLAMA_CPP_ROOT)/data

KQTYPES := Q2_K Q3_K_S Q3_K_M Q3_K_L Q4_K_S Q4_K_M Q5_K_S Q5_K_M Q6_K
IQTYPES := IQ2_XXS IQ2_XS IQ3_XS IQ3_XXS IQ1_S IQ3_S IQ3_M IQ2_S IQ2_M IQ4_XS
IQTYPES += Q2_K_S

QTYPES := Q8_0 $(KQTYPES) $(IQTYPES)

quantize := $(LLAMA_CPP_BIN)/quantize.exe
convert := python $(LLAMA_CPP_BIN)/convert.py
imatrix := $(LLAMA_CPP_BIN)/imatrix.exe -f $(LLAMA_CPP_DATA)/20k_random_data.txt

ifndef MODEL_ID
$(error MODEL_ID is not defined)
endif

MODEL_BASE := $(lastword $(subst /, ,$(MODEL_ID)))
ifeq ($(MODEL_BASE),$(MODEL_ID))
$(error MODEL_ID must be of the form author/name)
endif

MODEL_SIZE := $(patsubst -%B-,%,$(findstring -70B-,$(subst b,B,$(subst .,-,$(MODEL_BASE)))))
ifeq ($(MODEL_SIZE),70)
IMATQ := Q8_0
else
IMATQ := F16
endif

MODEL_DIR := $(MODEL_BASE)

KQUANTS := $(patsubst %,$(MODEL_BASE).%.gguf,$(KQTYPES))
kquants:: $(KQUANTS)

IQUANTS := $(patsubst %,$(MODEL_BASE).%.gguf,$(IQTYPES))
iquants:: $(IQUANTS)

QUANTS := $(patsubst %,$(MODEL_BASE).%.gguf,$(QTYPES))
quants:: $(QUANTS)

$(MODEL_DIR):
	huggingface-cli.exe download $(MODEL_ID) --local-dir $(MODEL_DIR)

%.F16.gguf: | $(MODEL_DIR)
	$(convert) $| --outtype f16 --outfile $@

imatrix.dat: | $(MODEL_BASE).$(IMATQ).gguf
	$(imatrix) -m $|

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
%.Q2_K_S.gguf: | imatrix.dat %.F16.gguf
	$(quantize) --imatrix $| $@ Q2_K_S
%.IQ2_XXS.gguf: | imatrix.dat %.F16.gguf
	$(quantize) --imatrix $| $@ IQ2_XXS
%.IQ2_XS.gguf: | imatrix.dat %.F16.gguf
	$(quantize) --imatrix $| $@ IQ2_XS
%.IQ3_XS.gguf: | imatrix.dat %.F16.gguf
	$(quantize) --imatrix $| $@ IQ3_XS
%.IQ3_XXS.gguf: | imatrix.dat %.F16.gguf
	$(quantize) --imatrix $| $@ IQ3_XXS
%.IQ1_S.gguf: | imatrix.dat %.F16.gguf
	$(quantize) --imatrix $| $@ IQ1_S
# %.IQ4_NL.gguf: | imatrix.dat %.F16.gguf
# 	$(quantize) --imatrix $| $@ IQ4_NL
%.IQ3_S.gguf: | imatrix.dat %.F16.gguf
	$(quantize) --imatrix $| $@ IQ3_S
%.IQ3_M.gguf: | imatrix.dat %.F16.gguf
	$(quantize) --imatrix $| $@ IQ3_M
%.IQ2_S.gguf: | imatrix.dat %.F16.gguf
	$(quantize) --imatrix $| $@ IQ2_S
%.IQ2_M.gguf: | imatrix.dat %.F16.gguf
	$(quantize) --imatrix $| $@ IQ2_M
%.IQ4_XS.gguf: | imatrix.dat %.F16.gguf
	$(quantize) --imatrix $| $@ IQ4_XS

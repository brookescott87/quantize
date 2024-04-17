LLAMA_CPP_ROOT := C:/Apps/Toaster
LLAMA_CPP_BIN := $(LLAMA_CPP_ROOT)/bin
LLAMA_CPP_DATA := $(LLAMA_CPP_ROOT)/data

KQTYPES := Q2_K Q3_K_S Q3_K_M Q3_K_L Q4_K_S Q4_K_M Q5_K_S Q5_K_M Q6_K
IQTYPES := IQ2_XXS IQ2_XS IQ3_XS IQ3_XXS IQ1_S IQ3_S IQ3_M IQ2_S IQ2_M IQ4_XS
IQTYPES += Q2_K_S

QTYPES := Q8_0 $(KQTYPES) $(IQTYPES)

qtype = $(subst .,,$(suffix $(patsubst %.gguf,%,$1)))

ifndef MODELS
MODELS := $(notdir $(wildcard models/*))
endif

xinstall = mkdir -p $3 && $1 $2 $3

ifdef INSTALL_DIR
VPATH := $(patsubst %,$(INSTALL_DIR)/%-GGUF,$(MODELS))
install = python install.py $3 $1 $(INSTALL_DIR)/$2
else
install = true
endif

# xquantize($1=out, $2=type, $3=in[, $4=imat])
xquantize = \
	$(LLAMA_CPP_BIN)/quantize.exe --background $(if $4,--imatrix $4) $3 $1 $2

# quantize($1=base, $2=ins, $3=out, $4=install opts)
quantize = \
	$(call xquantize,$3.tmp,$(call qtype,$3),$(filter %.gguf,$2),$(filter %.imatrix,$2)) && mv $3.tmp $3 && $(call install,$3,$1-GGUF,$4)

convert := python $(LLAMA_CPP_BIN)/convert.py --pad-vocab
imatrix := $(LLAMA_CPP_BIN)/imatrix.exe -f $(LLAMA_CPP_DATA)/20k_random_data.txt $(IMATRIX_OPTS)
imatrix_model := python imatrix_model.py

f16:: $(foreach m,$(MODELS),$m.F16.gguf)
q8:: $(foreach m,$(MODELS),$m.Q8_0.gguf)
imat:: $(foreach m,$(MODELS),$m.imatrix)

quants iquants:: f16 q8 imat
quants:: kquants iquants
kquants:: f16

kquants:: $(foreach m,$(MODELS),$(patsubst %,$m.%.gguf,$(KQTYPES)))
iquants:: $(foreach m,$(MODELS),$(patsubst %,$m.%.gguf,$(IQTYPES)))

%.F16.gguf: | models/%
	$(convert) $| --outtype f16 --outfile $@.tmp && mv $@.tmp $@ && $(call install,$@,$*-GGUF,-k)

%.imatrix: %.F16.gguf %.Q8_0.gguf
	$(imatrix) -o $@.tmp -m $(shell $(imatrix_model) $^) && mv $@.tmp $@ && $(call install,$@,$*-GGUF,-k)

.DELETE_ON_ERROR:

%.Q2_K.gguf: %.F16.gguf
	$(call quantize,$*,$^,$@)
%.Q3_K_S.gguf: %.F16.gguf
	$(call quantize,$*,$^,$@)
%.Q3_K_M.gguf: %.F16.gguf
	$(call quantize,$*,$^,$@)
%.Q3_K_L.gguf: %.F16.gguf
	$(call quantize,$*,$^,$@)
%.Q4_K_S.gguf: %.F16.gguf
	$(call quantize,$*,$^,$@)
%.Q4_K_M.gguf: %.F16.gguf
	$(call quantize,$*,$^,$@)
%.Q5_K_S.gguf: %.F16.gguf
	$(call quantize,$*,$^,$@)
%.Q5_K_M.gguf: %.F16.gguf
	$(call quantize,$*,$^,$@)
%.Q6_K.gguf: %.F16.gguf
	$(call quantize,$*,$^,$@)
%.Q8_0.gguf: %.F16.gguf
	$(call quantize,$*,$^,$@,-k)
%.Q2_K_S.gguf: %.F16.gguf %.imatrix
	$(call quantize,$*,$^,$@)
%.IQ2_XXS.gguf: %.F16.gguf %.imatrix
	$(call quantize,$*,$^,$@)
%.IQ2_XS.gguf: %.F16.gguf %.imatrix
	$(call quantize,$*,$^,$@)
%.IQ3_XS.gguf: %.F16.gguf %.imatrix
	$(call quantize,$*,$^,$@)
%.IQ3_XXS.gguf: %.F16.gguf %.imatrix
	$(call quantize,$*,$^,$@)
%.IQ1_S.gguf: %.F16.gguf %.imatrix
	$(call quantize,$*,$^,$@)
# %.IQ4_NL.gguf: %.F16.gguf %.imatrix
# 	$(call quantize,$*,$^,$@)
%.IQ3_S.gguf: %.F16.gguf %.imatrix
	$(call quantize,$*,$^,$@)
%.IQ3_M.gguf: %.F16.gguf %.imatrix
	$(call quantize,$*,$^,$@)
%.IQ2_S.gguf: %.F16.gguf %.imatrix
	$(call quantize,$*,$^,$@)
%.IQ2_M.gguf: %.F16.gguf %.imatrix
	$(call quantize,$*,$^,$@)
%.IQ4_XS.gguf: %.F16.gguf %.imatrix
	$(call quantize,$*,$^,$@)

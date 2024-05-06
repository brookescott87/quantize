SRCDIR := $(patsubst %/,%,$(dir $(lastword $(MAKEFILE_LIST))))
MODELBASE := $(SRCDIR)/models/base

ifndef TOASTER_ROOT
$(error TOASTER_ROOT is not set)
endif

export TOASTER_BIN := $(TOASTER_ROOT)/bin
export TOASTER_LIB := $(TOASTER_ROOT)/lib

KQTYPES := Q2_K Q3_K_S Q3_K_M Q3_K_L Q4_K_S Q4_K_M Q5_K_S Q5_K_M Q6_K
IQTYPES := IQ2_XXS IQ2_XS IQ3_XS IQ3_XXS IQ1_S IQ3_S IQ3_M IQ2_S IQ2_M IQ4_XS
IQTYPES += Q2_K_S

QTYPES := Q8_0 $(KQTYPES) $(IQTYPES)

qtype = $(subst .,,$(suffix $(patsubst %.gguf,%,$1)))
ifdef OUTPUT_REPO
OUTPUT_ROOT := output/$(OUTPUT_REPO)
qfile = $(patsubst %.imatrix.gguf,%.imatrix,$(foreach m,$1,$(foreach q,$2,$(OUTPUT_ROOT)/$m-GGUF/$m.$q.gguf)))
else
qfile = $(patsubst %.imatrix.gguf,%.imatrix,$(foreach m,$1,$(foreach q,$2,$m.$q.gguf)))
endif

ifndef MODELS
MODELS := $(notdir $(wildcard $(MODELBASE)/*))
endif

OUTPUTDIRS := $(if $(OUTPUT_ROOT),$(patsubst %,$(OUTPUT_ROOT)/%-GGUF,$(MODELS)))

listmodels::
	@echo "Models: $(MODELS)"

qfiles = $(call qfile,$(MODELS),$1)

xinstall = mkdir -p $3 && $1 $2 $3

ifdef INSTALL_DIR
VPATH := $(patsubst %,$(INSTALL_DIR)/%-GGUF,$(MODELS))
install = python $(SRCDIR)/install.py $3 $1 $(INSTALL_DIR)/$2
else
install = true
endif

# xquantize($1=out, $2=type, $3=in[, $4=imat])
xquantize = \
	$(TOASTER_BIN)/quantize $(if $4,--imatrix $4) $3 $1 $2

# quantize($1=base, $2=ins, $3=out, $4=install opts)
quantize = \
	$(call xquantize,$3,$(call qtype,$3),$(filter %.gguf,$2),$(filter %.imatrix,$2)) && $(call install,$3,$1-GGUF,$4)

xconvert = python $(TOASTER_BIN)/$1 --outtype $3 --outfile $4.tmp $(convert_opts) $2 && mv $4.tmp $4 

ifdef old_convert
convert_py := convert.py --pad-vocab
else
convert_py := convert-hf-to-gguf.py
endif

convert = $(call xconvert,$(convert_py),$1,$2,$3)
imatrix := $(TOASTER_BIN)/imatrix $(IMATRIX_OPTS)
imatrix_model := python $(SRCDIR)/imatrix_model.py
mkreadme := python $(SRCDIR)/mkreadme.py

ifdef ABORT
$(error Aborted)
endif

f32:: $(call qfiles,F32)
f16:: $(call qfiles,F16)
q8:: $(call qfiles,Q8_0)
imat:: $(call qfiles,imatrix)

kquants iquants:: f16 q8
iquants:: imat
quants:: kquants iquants
all:: quants

kquants:: $(call qfiles,$(KQTYPES))
iquants:: $(call qfiles,$(IQTYPES))

$(OUTPUTDIRS): $(OUTPUT_ROOT)/%-GGUF: | $(MODELBASE)/%
	mkdir -p $@
	$(mkreadme) -o $@ -f $| 

%.F32.gguf: $(OUTPUTDIRS)
	$(call convert,$(MODELBASE)/$(notdir $*),f32,$@)

%.F16.gguf: $(OUTPUTDIRS)
	$(call convert,$(MODELBASE)/$(notdir $*),f16,$@)

ifdef LOWMEM
%.imatrix:| %.F16.gguf %.Q8_0.gguf %.dataset.txt
	$(imatrix) -o $@.tmp -f $(filter %.txt,$|) -m $(shell $(imatrix_model) $(filter-out %.txt,$|)) && mv $@.tmp $@ && $(call install,$@,$*-GGUF,-k)
else
%.imatrix:| %.F16.gguf %.dataset.txt
	$(imatrix) -o $@.tmp -f $(filter %.txt,$|) -m $(filter-out %.txt,$|) && mv $@.tmp $@ && $(call install,$@,$*-GGUF,-k)
endif

%.dataset.txt: $(SRCDIR)/data/20k_random_data.txt
	cp $^ $@

.DELETE_ON_ERROR:

%.Q2_K.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q3_K_S.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q3_K_M.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q3_K_L.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q4_K_S.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q4_K_M.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q5_K_S.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q5_K_M.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q6_K.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q8_0.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@,-k)
%.Q2_K_S.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ2_XXS.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ2_XS.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ3_XS.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ3_XXS.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ1_S.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
# %.IQ4_NL.gguf:| %.F16.gguf %.imatrix
# 	$(call quantize,$*,$|,$@)
%.IQ3_S.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ3_M.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ2_S.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ2_M.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ4_XS.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)

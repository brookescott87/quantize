SRCDIR := $(patsubst %/,%,$(dir $(lastword $(MAKEFILE_LIST))))
MODELBASE := $(SRCDIR)/models/base

ifndef TOASTER_ROOT
$(error TOASTER_ROOT is not set)
endif

export TOASTER_BIN := $(TOASTER_ROOT)/bin
export TOASTER_LIB := $(TOASTER_ROOT)/lib

ifndef HF_ORGANIZATION
ifdef HF_DEFAULT_ORGANIZATION
export HF_ORGANIZATION := $(HF_DEFAULT_ORGANIZATION)
else
$(error HF_ORGANIZATION is not set)
endif
endif

export OUTPUT_ROOT := output/$(HF_ORGANIZATION)

QTYPES := IQ1_S IQ1_M IQ2_XXS IQ2_XS IQ2_S IQ2_M Q2_K_S Q2_K
QTYPES += IQ3_XXS IQ3_XS Q3_K_S IQ3_S IQ3_M Q3_K_M Q3_K_L IQ4_XS
QTYPES += Q4_K_S Q4_K_M Q5_K_S Q5_K_M Q6_K Q8_0

listqtypes::
	@echo $(QTYPES)

qtype = $(subst .,,$(suffix $(patsubst %.gguf,%,$1)))
qfile = $(patsubst %.imatrix.gguf,%.imatrix,$(foreach m,$1,$(foreach q,$2,$(OUTPUT_ROOT)/$m-GGUF/$m.$q.gguf)))

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
	$(TOASTER_BIN)/quantize --imatrix $4 $3 $1 $2

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
imatrix_data := $(patsubst ./%,%,$(SRCDIR)/imatrix.dataset.txt)
imatrix_model := python $(SRCDIR)/imatrix_model.py
imatrix := $(TOASTER_BIN)/imatrix -f $(imatrix_data) $(IMATRIX_OPTS)
mkreadme := python $(SRCDIR)/mkreadme.py

ifdef ABORT
$(error Aborted)
endif

f32:: $(call qfiles,F32)
f16:: $(call qfiles,F16)
q8:: $(call qfiles,Q8_0)
imat:: $(call qfiles,imatrix)

quants:: f16 imat
quants:: $(call qfiles,$(QTYPES))
all:: quants

$(OUTPUTDIRS): $(OUTPUT_ROOT)/%-GGUF: | $(MODELBASE)/%
	mkdir -p $@
	$(mkreadme) -o $@ -f $| 

%.F32.gguf:| $(OUTPUTDIRS)
	$(call convert,$(MODELBASE)/$(notdir $*),f32,$@)

%.F16.gguf:| $(OUTPUTDIRS)
	$(call convert,$(MODELBASE)/$(notdir $*),f16,$@)

ifdef LOWMEM
%.imatrix:| %.F16.gguf %.Q8_0.gguf
	$(imatrix) -o $@.tmp -m $(shell $(imatrix_model) $|) && mv $@.tmp $@ && $(call install,$@,$*-GGUF,-k)
else
%.imatrix:| %.F16.gguf
	$(imatrix) -o $@.tmp -m $| && mv $@.tmp $@ && $(call install,$@,$*-GGUF,-k)
endif

.DELETE_ON_ERROR:

%.Q2_K.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.Q3_K_S.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.Q3_K_M.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.Q3_K_L.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.Q4_K_S.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.Q4_K_M.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.Q5_K_S.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.Q5_K_M.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.Q6_K.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.Q8_0.gguf:| %.F16.gguf %.imatrix
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
